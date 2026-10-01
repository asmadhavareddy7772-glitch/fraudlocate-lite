"""
FraudLocate Lite - Interactive Folium Map Builder.
Renders multi-layered geospatial visualizations with DBSCAN clusters, centroids,
noise points, density heatmaps, and sequential patrol routes.
"""

from typing import Dict, Any, List, Optional, Tuple
import folium
from folium.plugins import HeatMap
import pandas as pd
import numpy as np
from src.clustering import NOISE_LABEL_STR

# Harmonious, high-contrast palette for clusters
CLUSTER_COLORS = [
    "#ef4444",  # Crimson Red
    "#3b82f6",  # Royal Blue
    "#10b981",  # Emerald Green
    "#f59e0b",  # Amber Orange
    "#8b5cf6",  # Purple Violet
    "#06b6d4",  # Cyan Blue
    "#ec4899",  # Hot Pink
    "#14b8a6",  # Teal
    "#f97316",  # Deep Orange
    "#6366f1",  # Indigo
]
NOISE_COLOR = "#94a3b8"  # Slate grey for unclustered points


def get_cluster_color(cluster_id: int) -> str:
    """Return distinct color for cluster_id or grey for noise."""
    if cluster_id == -1:
        return NOISE_COLOR
    return CLUSTER_COLORS[cluster_id % len(CLUSTER_COLORS)]


def create_folium_dashboard_map(
    df: pd.DataFrame,
    cluster_stats_df: Optional[pd.DataFrame] = None,
    patrol_route: Optional[Dict[str, Any]] = None,
    show_raw_points: bool = True,
    show_centroids: bool = True,
    show_radii: bool = True,
    show_heatmap: bool = True,
    show_patrol_route: bool = True,
    max_raw_points: int = 1500,
) -> folium.Map:
    """
    Build complete Folium Map with togglable layers for clusters, heatmaps, and patrol routes.

    Args:
        df: DataFrame containing transactions with cluster_id, latitude, longitude.
        cluster_stats_df: Ranked cluster stats containing centroid and metrics.
        patrol_route: Dict returned by build_nearest_neighbor_patrol_route.
        show_raw_points: Whether to render individual ATM cash-out points.
        show_centroids: Whether to mark cluster centroids.
        show_radii: Whether to render circular hotspot boundaries.
        show_heatmap: Whether to render density HeatMap layer.
        show_patrol_route: Whether to overlay suggested patrol route.
        max_raw_points: Max points to plot to prevent browser lag.

    Returns:
        folium.Map instance.
    """
    if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
        # Default fallback map centered on Hyderabad
        return folium.Map(location=[17.3850, 78.4867], zoom_start=11, tiles="OpenStreetMap")

    # Center map on data centroid
    center_lat = float(df["latitude"].mean())
    center_lon = float(df["longitude"].mean())

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # 1. HeatMap Layer (Density of all withdrawals)
    if show_heatmap and len(df) > 0:
        heat_data = df[["latitude", "longitude"]].values.tolist()
        heat_layer = folium.FeatureGroup(name="🔥 Withdrawal Intensity Heatmap", show=True)
        HeatMap(
            heat_data,
            radius=15,
            blur=18,
            max_zoom=14,
            min_opacity=0.35,
        ).add_to(heat_layer)
        heat_layer.add_to(fmap)

    # 2. Hotspot Cluster Boundaries & Centroids Layer
    if cluster_stats_df is not None and not cluster_stats_df.empty:
        hotspots_layer = folium.FeatureGroup(name="🎯 Hotspot Centroids & Radius", show=True)

        for _, c_row in cluster_stats_df.iterrows():
            c_id = int(c_row["cluster_id"])
            c_color = get_cluster_color(c_id)
            c_lat = float(c_row["centroid_lat"])
            c_lon = float(c_row["centroid_lon"])
            radius_km = float(c_row["approx_radius_km"])
            area = str(c_row.get("primary_area", "Zone"))
            txns = int(c_row.get("num_withdrawals", 0))
            atms = int(c_row.get("num_unique_atms", 0))
            tot_amt = float(c_row.get("total_withdrawal_amount", 0.0))
            avg_amt = float(c_row.get("avg_withdrawal_amount", 0.0))
            peak_hr = str(c_row.get("most_active_hour_str", "N/A"))
            peak_day = str(c_row.get("most_active_day", "N/A"))
            priority = str(c_row.get("priority_tier", "Normal"))
            score = float(c_row.get("priority_score", 0.0))

            popup_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; width: 250px; font-size: 13px; line-height: 1.4;">
                <div style="background-color: {c_color}; color: white; padding: 6px 10px; border-radius: 4px; font-weight: bold; margin-bottom: 8px;">
                    🎯 Hotspot #{c_id} — {area}
                </div>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="color: #64748b;">Priority:</td><td><b>{priority} ({score} pts)</b></td></tr>
                    <tr><td style="color: #64748b;">Withdrawals:</td><td><b>{txns:,}</b></td></tr>
                    <tr><td style="color: #64748b;">Unique ATMs:</td><td><b>{atms}</b></td></tr>
                    <tr><td style="color: #64748b;">Total Amount:</td><td><b>₹{tot_amt:,.0f}</b></td></tr>
                    <tr><td style="color: #64748b;">Avg Amount:</td><td><b>₹{avg_amt:,.0f}</b></td></tr>
                    <tr><td style="color: #64748b;">Peak Window:</td><td><b>{peak_hr}</b></td></tr>
                    <tr><td style="color: #64748b;">Peak Day:</td><td><b>{peak_day}</b></td></tr>
                    <tr><td style="color: #64748b;">Cluster Radius:</td><td><b>~{radius_km:.2f} km</b></td></tr>
                </table>
            </div>
            """

            # Hotspot boundary circle (radius in meters)
            if show_radii:
                folium.Circle(
                    location=[c_lat, c_lon],
                    radius=radius_km * 1000.0,
                    color=c_color,
                    weight=2,
                    fill=True,
                    fill_color=c_color,
                    fill_opacity=0.15,
                    dash_array="5, 5",
                    tooltip=f"Hotspot #{c_id} ({area}) - Radius ~{radius_km:.2f} km",
                ).add_to(hotspots_layer)

            # Centroid Marker
            if show_centroids:
                folium.Marker(
                    location=[c_lat, c_lon],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"<b>Hotspot #{c_id}</b> ({area}) | Priority: {priority}",
                    icon=folium.Icon(color="darkblue", icon="bullseye", prefix="fa"),
                ).add_to(hotspots_layer)

        hotspots_layer.add_to(fmap)

    # 3. Raw Withdrawal Points Layer
    if show_raw_points and len(df) > 0:
        raw_pts_layer = folium.FeatureGroup(name="📍 Individual ATM Withdrawals", show=True)
        # Sample points if dataset is very large to keep browser fast and responsive
        plot_df = df.sample(n=min(len(df), max_raw_points), random_state=42) if len(df) > max_raw_points else df

        for _, row in plot_df.iterrows():
            c_id = int(row.get("cluster_id", -1))
            p_lat = float(row["latitude"])
            p_lon = float(row["longitude"])
            color = get_cluster_color(c_id)
            is_noise = (c_id == -1)

            atm_name = row.get("atm_name", "ATM")
            atm_id = row.get("atm_id", "N/A")
            amount = row.get("withdrawal_amount", 0)
            date_str = row.get("date", "")
            time_str = row.get("time", "")
            cluster_text = f"Hotspot #{c_id}" if not is_noise else NOISE_LABEL_STR

            point_popup = f"""
            <div style="font-family: sans-serif; font-size: 12px; width: 200px;">
                <b>{atm_name}</b> ({atm_id})<br>
                <span style="color: {'#dc2626' if not is_noise else '#64748b'}; font-weight: bold;">{cluster_text}</span><br>
                Amount: <b>₹{amount:,.0f}</b><br>
                Time: {date_str} {time_str}
            </div>
            """

            folium.CircleMarker(
                location=[p_lat, p_lon],
                radius=3 if is_noise else 4.5,
                color=color,
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.6 if is_noise else 0.85,
                popup=folium.Popup(point_popup, max_width=240),
                tooltip=f"{cluster_text} | ₹{amount:,.0f}",
            ).add_to(raw_pts_layer)

        raw_pts_layer.add_to(fmap)

    # 4. Patrol Route Layer
    if show_patrol_route and patrol_route and len(patrol_route.get("stops", [])) > 1:
        route_layer = folium.FeatureGroup(name="🚔 Suggested Patrol Route", show=True)
        waypoints = patrol_route.get("waypoints_coords", [])

        # Polyline connecting sequence
        folium.PolyLine(
            locations=waypoints,
            color="#2563eb",
            weight=4.5,
            opacity=0.88,
            dash_array="8, 6",
            tooltip=f"Patrol Route ({patrol_route.get('total_distance_km')} km)",
        ).add_to(route_layer)

        # Numbered stop markers
        for stop in patrol_route.get("stops", []):
            s_num = stop["stop_number"]
            s_lat = stop["lat"]
            s_lon = stop["lon"]
            s_name = stop["name"]
            is_base = stop["is_base"]

            stop_popup = f"""
            <div style="font-family: sans-serif; font-size: 13px; width: 220px;">
                <div style="background-color: #1e3a8a; color: white; padding: 4px 8px; border-radius: 3px; font-weight: bold;">
                    Stop #{s_num}: {s_name}
                </div>
                <div style="padding-top: 6px;">
                    Leg Distance: <b>{stop['leg_distance_km']} km</b><br>
                    Cumulative Distance: <b>{stop['cumulative_distance_km']} km</b><br>
                    Est. Travel Time: <b>{stop['cumulative_time_minutes']} min</b>
                </div>
            </div>
            """

            if is_base:
                folium.Marker(
                    location=[s_lat, s_lon],
                    popup=folium.Popup(stop_popup, max_width=260),
                    tooltip=f"Base: {s_name}",
                    icon=folium.Icon(color="black", icon="home", prefix="fa"),
                ).add_to(route_layer)
            else:
                folium.Marker(
                    location=[s_lat, s_lon],
                    popup=folium.Popup(stop_popup, max_width=260),
                    tooltip=f"Stop #{s_num}: {s_name}",
                    icon=folium.Icon(color="red", icon="flag", prefix="fa"),
                ).add_to(route_layer)

        route_layer.add_to(fmap)

    # Layer control toggle
    folium.LayerControl(position="topright", collapsed=False).add_to(fmap)

    return fmap
