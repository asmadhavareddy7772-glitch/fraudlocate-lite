"""
FraudLocate Lite - Dedicated Police Alert Dashboard & Tactical Response Terminal.
Designed to be operated on a law-enforcement monitoring terminal (Laptop 2)
with real-time alert feed, evidence preview, geospatial ATM focus map,
historical withdrawal correlation, 7-stage incident timeline, and lifecycle status management.
Single source of truth: SQLite alerts database.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.alert_store import (
    get_all_alerts,
    get_new_alerts,
    get_reviewed_alerts,
    get_resolved_alerts,
    get_alert_by_id,
    update_alert_status,
    mark_alert_reviewed,
    mark_alert_resolved,
    get_alert_statistics,
    VALID_STATUSES,
)
from src.distance import haversine_distance_km, calculate_travel_time
from src.route_optimizer import DEFAULT_HQ_COORDS
from src.notification_service import generate_google_maps_link, generate_osm_link


def render_html(html_str: str) -> None:
    """Render raw HTML safely without triggering Markdown code syntax highlighters."""
    clean_html = "\n".join(line.strip() for line in html_str.strip().splitlines())
    if hasattr(st, "html"):
        st.html(clean_html)
    else:
        st.markdown(clean_html, unsafe_allow_html=True)


def create_police_focus_map(
    alert: Dict[str, Any],
    ranked_hotspots_df: Optional[pd.DataFrame] = None,
    nearby_txns_df: Optional[pd.DataFrame] = None,
) -> folium.Map:
    """
    Generate an operational tactical map focused on the alert ATM,
    its surrounding hotspot cluster radius, nearby transactions, and route from Command HQ.
    """
    atm_lat = float(alert.get("latitude", 17.3850))
    atm_lon = float(alert.get("longitude", 78.4867))
    atm_id = alert.get("atm_id", "ATM")
    atm_name = alert.get("atm_name", "Kiosk")
    area = alert.get("area", "Sector")
    severity = alert.get("severity", "High Priority")
    cluster_id = int(alert.get("cluster_id", -1))

    hq_lat = float(DEFAULT_HQ_COORDS["lat"])
    hq_lon = float(DEFAULT_HQ_COORDS["lon"])

    mid_lat = (atm_lat + hq_lat) / 2.0
    mid_lon = (atm_lon + hq_lon) / 2.0

    fmap = folium.Map(
        location=[mid_lat, mid_lon],
        zoom_start=13,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # 1. Police Command HQ Marker
    folium.Marker(
        location=[hq_lat, hq_lon],
        popup=f"<b>{DEFAULT_HQ_COORDS['name']}</b><br>{DEFAULT_HQ_COORDS['area']}",
        tooltip="Police Command Base HQ",
        icon=folium.Icon(color="blue", icon="shield", prefix="fa"),
    ).add_to(fmap)

    # 2. Alert ATM Marker (High-visibility Red Bullseye)
    atm_popup = f"""
    <div style="font-family: sans-serif; font-size: 13px; width: 230px;">
        <div style="background-color: #ef4444; color: white; padding: 6px; border-radius: 4px; font-weight: bold;">
            🚨 ALERT ATM: {atm_id}
        </div>
        <div style="padding-top: 6px; color: #1e293b;">
            <b>{atm_name}</b><br>
            Area: {area}<br>
            Severity: <span style="color: #dc2626; font-weight: bold;">{severity}</span><br>
            Alert ID: {alert.get('alert_id')}
        </div>
    </div>
    """

    folium.Marker(
        location=[atm_lat, atm_lon],
        popup=folium.Popup(atm_popup, max_width=260),
        tooltip=f"TARGET ATM: {atm_id} ({area})",
        icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa"),
    ).add_to(fmap)

    # 3. Hotspot Cluster Boundary Circle (if clustered)
    if cluster_id != -1 and ranked_hotspots_df is not None and not ranked_hotspots_df.empty:
        c_match = ranked_hotspots_df[ranked_hotspots_df["cluster_id"] == cluster_id]
        if not c_match.empty:
            c_row = c_match.iloc[0]
            c_lat = float(c_row["centroid_lat"])
            c_lon = float(c_row["centroid_lon"])
            radius_m = float(c_row.get("approx_radius_km", 0.5)) * 1000.0

            folium.Circle(
                location=[c_lat, c_lon],
                radius=radius_m,
                color="#f59e0b",
                weight=2.5,
                fill=True,
                fill_color="#f59e0b",
                fill_opacity=0.18,
                dash_array="6, 6",
                tooltip=f"Historical DBSCAN Hotspot #{cluster_id} (Score: {c_row.get('priority_score')} pts)",
            ).add_to(fmap)

            folium.Marker(
                location=[c_lat, c_lon],
                tooltip=f"Hotspot #{cluster_id} Centroid",
                icon=folium.Icon(color="orange", icon="bullseye", prefix="fa"),
            ).add_to(fmap)

    # 4. Connecting Patrol Dispatch Line from HQ
    patrol_dist_km = haversine_distance_km(hq_lat, hq_lon, atm_lat, atm_lon)
    travel_info = calculate_travel_time(patrol_dist_km, speed_kmh=40.0)

    folium.PolyLine(
        locations=[[hq_lat, hq_lon], [atm_lat, atm_lon]],
        color="#38bdf8",
        weight=3.5,
        opacity=0.85,
        dash_array="5, 8",
        tooltip=f"Dispatch Vector: {patrol_dist_km:.2f} km (~{travel_info['formatted_time']})",
    ).add_to(fmap)

    # 5. Nearby Historical Withdrawals Points (if available)
    if nearby_txns_df is not None and not nearby_txns_df.empty:
        for _, n_row in nearby_txns_df.head(60).iterrows():
            folium.CircleMarker(
                location=[float(n_row["latitude"]), float(n_row["longitude"])],
                radius=3.5,
                color="#64748b",
                fill=True,
                fill_color="#94a3b8",
                fill_opacity=0.6,
                tooltip=f"Historical Txn: ₹{n_row.get('withdrawal_amount', 0):,.0f} ({n_row.get('time', '')})",
            ).add_to(fmap)

    return fmap


def render_incident_timeline_component(timeline_dict: Dict[str, Any]) -> str:
    """Render HTML markup for the 7-stage incident timeline."""
    steps = [
        ("Evidence Uploaded", timeline_dict.get("evidence_uploaded")),
        ("Evidence Processed", timeline_dict.get("evidence_processed")),
        ("Fraud Event Created", timeline_dict.get("fraud_event_created")),
        ("Alert Generated", timeline_dict.get("alert_generated")),
        ("Police Notified", timeline_dict.get("police_notified")),
        ("Alert Reviewed", timeline_dict.get("alert_reviewed")),
        ("Case Status Updated", timeline_dict.get("case_status_updated")),
    ]

    html_parts = [
        """
        <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 14px; margin-bottom: 16px;">
            <div style="font-size: 13px; font-weight: 700; color: #38bdf8; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.5px;">
                ⏱️ Chronological Incident & Police Response Timeline
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
        """
    ]

    for title, ts in steps:
        is_done = bool(ts)
        badge_color = "#10b981" if is_done else "#64748b"
        icon = "✓" if is_done else "○"
        ts_text = ts if ts else "Pending Action"
        font_weight = "bold" if is_done else "normal"

        html_parts.append(
            f"""
            <div style="display: flex; align-items: center; justify-content: space-between; font-size: 12px; border-bottom: 1px solid rgba(148, 163, 184, 0.1); padding-bottom: 4px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: {badge_color}; color: white; width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold;">
                        {icon}
                    </span>
                    <span style="color: {'#f1f5f9' if is_done else '#94a3b8'}; font-weight: {font_weight};">
                        {title}
                    </span>
                </div>
                <span style="color: {'#38bdf8' if is_done else '#64748b'}; font-family: monospace; font-size: 11px;">
                    {ts_text}
                </span>
            </div>
            """
        )

    html_parts.append("</div></div>")
    return "".join(html_parts)
