"""
FraudLocate Lite — Cyber-Fraud Withdrawal Hotspot & Patrol Coverage Analytics (PS-024)
Problem Statement ID: PS-024 | Domain: Data Science & Predictive Analytics

A streamlined law-enforcement decision-support system implementing the complete workflow:
Evidence Upload (Photo/Video) -> Fraud Event Analysis -> Police Alert -> Email Dispatch -> Clickable Map Location.

ZERO technical or debug code is exposed on the user interface.
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import streamlit as st
from streamlit_folium import st_folium
import folium

# Core Analytics & Data Pipeline
from src.data_loader import (
    load_withdrawal_dataset,
    convert_df_to_csv_bytes,
    DEFAULT_DATA_PATH,
)
from src.preprocessing import validate_and_preprocess
from src.clustering import run_dbscan_clustering, NOISE_LABEL_STR
from src.hotspot_analysis import compute_cluster_statistics, rank_hotspots
from src.time_analysis import DAYS_OF_WEEK_ORDER
from src.route_optimizer import (
    build_nearest_neighbor_patrol_route,
    DEFAULT_HQ_COORDS,
)
from src.visualization import create_folium_dashboard_map

# Alert Store & Persistence
from src.alert_store import (
    init_alert_db,
    insert_alert,
    get_all_alerts,
    get_active_alerts,
    get_alerts_by_status,
    get_alert_by_id,
    update_alert_status,
    mark_alert_reviewed,
    get_alert_statistics,
    seed_demo_alerts_if_empty,
    VALID_STATUSES,
)

# Evidence Processing & Notification
from src.evidence_processor import (
    generate_evidence_id,
    generate_case_id,
    save_uploaded_evidence,
    extract_media_metadata,
    process_fraud_evidence,
    simulate_fraud_event,
)
from src.notification_service import (
    get_email_config,
    is_smtp_configured,
    get_notification_logs,
    send_fraud_alert_email,
    generate_google_maps_link,
    generate_osm_link,
    format_alert_email_text,
    format_alert_email_html,
    DEFAULT_ALERT_SUBJECT,
)
from src.police_dashboard import create_police_focus_map
from src.reports import (
    generate_incident_report_df,
    generate_alert_report_df,
    generate_evidence_report_df,
)
from utils.sample_evidence_generator import ensure_sample_evidence_exists, SAMPLE_DIR
from utils.data_generator import save_synthetic_dataset

# -----------------------------------------------------------------------------
# 1. PAGE SETUP & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="FraudLocate Lite — Police Alert System",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Header Card */
    .app-header {
        background: linear-gradient(135deg, #090d16 0%, #1e293b 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 20px 26px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    }
    
    .app-title {
        font-size: 26px;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
        letter-spacing: -0.5px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .app-badge {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.5);
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .app-subtitle {
        font-size: 13px;
        color: #94a3b8;
        margin-top: 6px;
        margin-bottom: 0;
    }
    
    /* Academic Disclaimer Banner */
    .demo-banner {
        background: rgba(30, 41, 59, 0.6);
        border-left: 4px solid #38bdf8;
        border-radius: 0 8px 8px 0;
        padding: 10px 16px;
        margin-bottom: 16px;
        font-size: 12px;
        color: #cbd5e1;
        line-height: 1.5;
    }
    
    /* Workflow Flow Ribbon */
    .workflow-ribbon {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(51, 65, 85, 0.8);
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 20px;
        overflow-x: auto;
        gap: 8px;
    }
    
    .workflow-step {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        font-weight: 600;
        color: #94a3b8;
        white-space: nowrap;
    }
    
    .workflow-step.active {
        color: #38bdf8;
    }
    
    .workflow-step.alert {
        color: #f87171;
    }
    
    .workflow-step.done {
        color: #10b981;
    }
    
    .workflow-dot {
        width: 22px;
        height: 22px;
        border-radius: 50%;
        background: #334155;
        color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        font-weight: bold;
    }
    
    .workflow-dot.active {
        background: #0284c7;
    }
    
    .workflow-dot.alert {
        background: #dc2626;
    }
    
    .workflow-dot.done {
        background: #059669;
    }
    
    /* KPI Card */
    .kpi-card-box {
        background: rgba(30, 41, 59, 0.75);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    
    .kpi-card-title {
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        color: #94a3b8;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    
    .kpi-card-value {
        font-size: 26px;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
    }
    
    .kpi-card-sub {
        font-size: 11px;
        color: #38bdf8;
        margin-top: 4px;
    }
    
    /* Alert Card (Section 8) */
    .police-alert-card {
        background: rgba(30, 41, 59, 0.85);
        border: 1px solid rgba(239, 68, 68, 0.4);
        border-left: 5px solid #ef4444;
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 14px;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
    }
    
    .police-alert-title {
        font-size: 16px;
        font-weight: 800;
        color: #f87171;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .police-alert-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px 16px;
        font-size: 13px;
        color: #cbd5e1;
        margin-bottom: 14px;
    }
    
    .police-alert-item b {
        color: #f8fafc;
    }
    
    .coord-tag {
        color: #38bdf8;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-weight: 700;
    }
    
    /* Action Button Link */
    .map-btn-link {
        display: inline-block;
        background-color: #ef4444;
        color: #ffffff !important;
        font-weight: 700;
        font-size: 13px;
        padding: 8px 16px;
        border-radius: 6px;
        text-decoration: none;
        box-shadow: 0 2px 8px rgba(239, 68, 68, 0.35);
        transition: background-color 0.2s ease;
    }
    
    .map-btn-link:hover {
        background-color: #dc2626;
        color: #ffffff !important;
    }
    
    /* Clean Email Preview Card */
    .email-preview-card {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 20px;
        margin-top: 14px;
        font-size: 13px;
        color: #e2e8f0;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. STATE & DATABASE INITIALIZATION
# -----------------------------------------------------------------------------
ensure_sample_evidence_exists()
init_alert_db()
seed_demo_alerts_if_empty()

if "active_evidence_path" not in st.session_state:
    st.session_state.active_evidence_path = os.path.join(SAMPLE_DIR, "sample_cctv_1.jpg")

if "active_evidence_id" not in st.session_state:
    st.session_state.active_evidence_id = "EVD-2026-48291"

if "last_detection" not in st.session_state:
    st.session_state.last_detection = None

if "last_email_record" not in st.session_state:
    st.session_state.last_email_record = None

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "🚨 Fraud Evidence & Alert"

if "selected_view_evidence_id" not in st.session_state:
    st.session_state.selected_view_evidence_id = None

# Initialize requested session_state variables
if "alerts" not in st.session_state:
    st.session_state.alerts = []

if "evidence" not in st.session_state:
    st.session_state.evidence = None

if "selected_alert" not in st.session_state:
    st.session_state.selected_alert = None

if "dbscan_df" not in st.session_state:
    st.session_state.dbscan_df = None

if "cluster_centroids" not in st.session_state:
    st.session_state.cluster_centroids = {}

if "cluster_radii" not in st.session_state:
    st.session_state.cluster_radii = {}

if "cluster_stats" not in st.session_state:
    st.session_state.cluster_stats = None

if "patrol_route" not in st.session_state:
    st.session_state.patrol_route = None

# Load dataset for ATM coordinates and secondary hotspot analytics
@st.cache_data(show_spinner=False)
def get_cached_raw_data() -> pd.DataFrame:
    try:
        return load_withdrawal_dataset(auto_generate_if_missing=True, default_records=2500, city="Hyderabad")
    except Exception as err:
        logger.error(f"Error loading withdrawal dataset: {err}")
        return pd.DataFrame()

try:
    raw_df = get_cached_raw_data()
    clean_df, _ = validate_and_preprocess(raw_df)

    if clean_df.empty:
        raise ValueError("Dataset is empty after preprocessing.")

    # Run DBSCAN once for secondary hotspot context
    dbscan_df, cluster_summary = run_dbscan_clustering(clean_df, radius_km=1.0, min_samples=5)
    cluster_centroids = cluster_summary.get("cluster_centroids", {})
    cluster_radii = cluster_summary.get("cluster_radii_km", {})

    cluster_stats_df = compute_cluster_statistics(
        dbscan_df,
        cluster_centroids=cluster_centroids,
        cluster_radii_km=cluster_radii,
    )
    ranked_hotspots_df = rank_hotspots(cluster_stats_df)

    default_patrol_route = build_nearest_neighbor_patrol_route(
        ranked_hotspots_df,
        start_point=DEFAULT_HQ_COORDS,
        speed_kmh=40.0,
        return_to_start=True,
        top_n=5,
    )

    atm_options_df = (
        clean_df[["atm_id", "atm_name", "area", "city", "latitude", "longitude"]]
        .drop_duplicates(subset=["atm_id"])
        .sort_values("area")
        .reset_index(drop=True)
    )

    # Persist in session state
    st.session_state.dbscan_df = dbscan_df
    st.session_state.cluster_centroids = cluster_centroids
    st.session_state.cluster_radii = cluster_radii
    st.session_state.cluster_stats = cluster_stats_df
    st.session_state.patrol_route = default_patrol_route

except Exception as ex:
    logger.warning(f"Hotspot clustering running with safe empty fallback: {ex}")
    clean_df = pd.DataFrame(columns=["atm_id", "atm_name", "area", "city", "latitude", "longitude"])
    dbscan_df = pd.DataFrame()
    cluster_summary = {}
    cluster_centroids = {}
    cluster_radii = {}
    cluster_stats_df = pd.DataFrame()
    ranked_hotspots_df = pd.DataFrame()
    default_patrol_route = build_nearest_neighbor_patrol_route(ranked_hotspots_df)
    atm_options_df = pd.DataFrame([
        {
            "atm_id": "ATM-HYD-001",
            "atm_name": "State Bank Kiosk - Hitech City",
            "area": "Madhapur",
            "city": "Hyderabad",
            "latitude": 17.4486,
            "longitude": 78.3908,
        }
    ])

# -----------------------------------------------------------------------------
# 3. HEADER & ETHICAL NOTICE
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div>
                <h1 class="app-title">
                    🛡️ FraudLocate Lite
                    <span class="app-badge">Police Alert System</span>
                </h1>
                <p class="app-subtitle">
                    Automated Cyber-Fraud Withdrawal Detection, Police Email Notification & Map Location Dispatch
                </p>
            </div>
            <div>
                <span class="app-badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981; border-color: rgba(16, 185, 129, 0.4);">
                    System Active: Ready for Review
                </span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="demo-banner">
        <b>⚖️ ACADEMIC PROTOTYPE NOTICE:</b>
        FraudLocate Lite is a synthetic-data decision-support prototype developed for academic and demonstration purposes.
        The system demonstrates automated evidence correlation, police alerting, and location mapping.
        It does not connect to live biometric surveillance and does not identify real individuals.
    </div>
    """,
    unsafe_allow_html=True,
)

# Visual Workflow Ribbon (Section 1 & 18)
st.markdown(
    """
    <div class="workflow-ribbon">
        <div class="workflow-step active"><span class="workflow-dot active">1</span> Upload Evidence</div>
        <span style="color: #475569;">➔</span>
        <div class="workflow-step active"><span class="workflow-dot active">2</span> Analyze Evidence</div>
        <span style="color: #475569;">➔</span>
        <div class="workflow-step alert"><span class="workflow-dot alert">3</span> Fraud Event Detected</div>
        <span style="color: #475569;">➔</span>
        <div class="workflow-step alert"><span class="workflow-dot alert">4</span> Police Alert Generated</div>
        <span style="color: #475569;">➔</span>
        <div class="workflow-step done"><span class="workflow-dot done">5</span> Police Email Sent</div>
        <span style="color: #475569;">➔</span>
        <div class="workflow-step done"><span class="workflow-dot done">6</span> View Location on Map</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 4. MAIN NAVIGATION TABS
# -----------------------------------------------------------------------------
tab_labels = [
    "🚨 Fraud Evidence & Alert",
    "🚔 Police Alert Dashboard",
    "📍 Hotspot & Patrol Analytics",
    "📑 Incident Reports",
]

tabs = st.tabs(tab_labels)

# =============================================================================
# TAB 1: 🚨 FRAUD EVIDENCE & POLICE ALERT (MAIN WORKFLOW)
# =============================================================================
with tabs[0]:
    # ONE-CLICK SIMULATION BUTTON (Section 11)
    sim_col1, sim_col2 = st.columns([7, 3])
    with sim_col1:
        st.markdown("### 📤 Fraud Evidence Upload & Analysis")
        st.caption("Upload photos or videos of ATM activity to detect potential fraud and dispatch police alerts.")
    with sim_col2:
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        if st.button("⚡ SIMULATE FRAUD ALERT", type="primary", use_container_width=True, help="One-click demonstration: select sample evidence, detect fraud, create alert, send email, and generate map link."):
            with st.spinner("Executing end-to-end fraud detection and police notification pipeline..."):
                sim_res = simulate_fraud_event(
                    historical_df=clean_df,
                    ranked_hotspots_df=ranked_hotspots_df,
                    sample_type="Image",
                )
                st.session_state.last_detection = sim_res
                st.session_state.last_email_record = sim_res.get("email_dispatch")
                st.session_state.active_evidence_path = sim_res.get("alert_data", {}).get("evidence_path", st.session_state.active_evidence_path)
                st.session_state.active_evidence_id = sim_res.get("evidence_id", "EVD-2026-48291")
                st.success("Fraud event detected! Police alert created and notification sent.")
                st.rerun()

    st.markdown("---")

    # Step 1: Upload Fraud Photo / Video
    u_left, u_right = st.columns([6, 4])

    with u_left:
        st.markdown("#### Step 1: Evidence Input")
        st.markdown("**Select Sample Evidence for Demonstration:**")
        preset_cols = st.columns(4)
        with preset_cols[0]:
            if st.button("📷 CCTV Photo", use_container_width=True):
                st.session_state.active_evidence_path = os.path.join(SAMPLE_DIR, "sample_cctv_1.jpg")
                st.session_state.active_evidence_id = generate_evidence_id()
                st.rerun()
        with preset_cols[1]:
            if st.button("🌙 Night CCTV", use_container_width=True):
                st.session_state.active_evidence_path = os.path.join(SAMPLE_DIR, "sample_cctv_2.jpg")
                st.session_state.active_evidence_id = generate_evidence_id()
                st.rerun()
        with preset_cols[2]:
            if st.button("🏢 ATM Photo", use_container_width=True):
                st.session_state.active_evidence_path = os.path.join(SAMPLE_DIR, "sample_atm_kiosk.jpg")
                st.session_state.active_evidence_id = generate_evidence_id()
                st.rerun()
        with preset_cols[3]:
            if st.button("🎥 CCTV Video", use_container_width=True):
                st.session_state.active_evidence_path = os.path.join(SAMPLE_DIR, "sample_cctv_clip.mp4")
                st.session_state.active_evidence_id = generate_evidence_id()
                st.rerun()

        uploaded_file = st.file_uploader(
            "Or drag and drop photo or video evidence:",
            type=["jpg", "jpeg", "png", "mp4", "avi", "mov"],
            help="Supported: ATM photos, CCTV screenshots, surveillance videos",
        )

        if uploaded_file is not None:
            orig_name = getattr(uploaded_file, "name", "")
            file_ext = os.path.splitext(orig_name)[1].lower().replace(".", "")
            if file_ext not in ["jpg", "jpeg", "png", "mp4", "avi", "mov"]:
                st.error("Unsupported file format.")
            else:
                new_eid = generate_evidence_id()
                saved_p = save_uploaded_evidence(uploaded_file, new_eid)
                st.session_state.active_evidence_path = saved_p
                st.session_state.active_evidence_id = new_eid
                st.success(f"File uploaded successfully! Evidence ID: {new_eid}")

        # Live Evidence Preview
        active_p = st.session_state.active_evidence_path
        if os.path.exists(active_p):
            st.markdown(f"**Evidence Preview:** `{os.path.basename(active_p)}`")
            _, ext = os.path.splitext(active_p)
            if ext.lower() in [".mp4", ".avi", ".mov"]:
                st.video(active_p)
            else:
                st.image(active_p, use_container_width=True)

    with u_right:
        st.markdown("#### Step 2: Location & Incident Context")

        meta = extract_media_metadata(st.session_state.active_evidence_path)
        cur_file_name = os.path.basename(st.session_state.active_evidence_path)
        cur_time_str = datetime.now().strftime("%I:%M:%S %p")

        st.markdown(
            f"""
            <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid #334155; border-radius: 8px; padding: 14px; margin-bottom: 14px; font-size: 13px;">
                <div style="margin-bottom: 6px;"><b>Evidence ID:</b> <code style="color: #38bdf8;">{st.session_state.active_evidence_id}</code></div>
                <div style="margin-bottom: 6px;"><b>File Name:</b> {cur_file_name}</div>
                <div style="margin-bottom: 6px;"><b>Evidence Type:</b> {meta.get('media_type', 'Image')} ({meta.get('extension', 'jpg').upper()})</div>
                <div><b>Upload Time:</b> {cur_time_str}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        atm_labels = [
            f"{row['atm_id']} — {row['atm_name']} ({row['area']})"
            for _, row in atm_options_df.iterrows()
        ]
        chosen_atm_label = st.selectbox("Associated ATM Kiosk:", atm_labels, index=0)
        chosen_row = atm_options_df.iloc[atm_labels.index(chosen_atm_label)]

        target_lat = float(chosen_row["latitude"])
        target_lon = float(chosen_row["longitude"])
        target_lat_str = f"{target_lat:.6f}"
        target_lon_str = f"{target_lon:.6f}"

        st.markdown(
            f"""
            <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid #334155; border-radius: 8px; padding: 14px; margin-bottom: 16px; font-size: 13px;">
                <div style="color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 11px; margin-bottom: 6px;">Kiosk Location Coordinates</div>
                <div><b>ATM ID:</b> {chosen_row['atm_id']}</div>
                <div><b>Area:</b> {chosen_row['area']}, {chosen_row['city']}</div>
                <div><b>Latitude:</b> <span class="coord-tag">{target_lat_str}</span></div>
                <div><b>Longitude:</b> <span class="coord-tag">{target_lon_str}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # Main Analyze Button
        if st.button("🔍 ANALYZE FRAUD EVIDENCE", type="primary", use_container_width=True):
            with st.spinner("Analyzing evidence and correlating with ATM location..."):
                det_res = process_fraud_evidence(
                    file_path=st.session_state.active_evidence_path,
                    atm_info=chosen_row.to_dict(),
                    complaint_id=generate_case_id(),
                    evidence_id=st.session_state.active_evidence_id,
                    flagged_amount=35000.0,
                    ranked_hotspots_df=ranked_hotspots_df,
                    historical_df=clean_df,
                )
                st.session_state.last_detection = det_res
                st.session_state.last_email_record = det_res.get("email_dispatch")
                st.success("Analysis completed! Potential fraud event confirmed.")
                st.rerun()

    # -------------------------------------------------------------------------
    # FRAUD EVENT RESULT (Section 3)
    # -------------------------------------------------------------------------
    if st.session_state.last_detection:
        det = st.session_state.last_detection
        alert_info = det.get("alert_data", {})
        atm_lat = float(alert_info.get("latitude", 17.4486))
        atm_lon = float(alert_info.get("longitude", 78.3908))
        lat_formatted = f"{atm_lat:.6f}"
        lon_formatted = f"{atm_lon:.6f}"
        google_maps_url = generate_google_maps_link(atm_lat, atm_lon)
        osm_url = generate_osm_link(atm_lat, atm_lon)

        st.markdown("---")
        st.markdown("### 🚨 Fraud Event Result")

        r_card_left, r_card_right = st.columns([6, 4])

        with r_card_left:
            st.markdown(
                f"""
                <div style="background: rgba(30, 41, 59, 0.95); border: 2px solid #ef4444; border-radius: 12px; padding: 22px; box-shadow: 0 8px 24px rgba(239, 68, 68, 0.2);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span style="font-size: 18px; font-weight: 800; color: #f87171;">
                            🚨 POTENTIAL FRAUD EVENT DETECTED
                        </span>
                        <span style="background: rgba(239, 68, 68, 0.25); color: #fca5a5; border: 1px solid #ef4444; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: bold;">
                            Status: Alert Generated
                        </span>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px 16px; font-size: 14px; margin-bottom: 18px;">
                        <div><span style="color: #94a3b8;">Alert ID:</span> <b>{alert_info.get('alert_id')}</b></div>
                        <div><span style="color: #94a3b8;">Evidence Type:</span> <b>{alert_info.get('evidence_type')}</b></div>
                        <div><span style="color: #94a3b8;">ATM:</span> <b>{alert_info.get('atm_id')} ({alert_info.get('atm_name')})</b></div>
                        <div><span style="color: #94a3b8;">Location:</span> <b>{alert_info.get('area')}, {alert_info.get('city')}</b></div>
                        <div><span style="color: #94a3b8;">Detection Time:</span> <b>{alert_info.get('timestamp')}</b></div>
                        <div><span style="color: #94a3b8;">Flagged Amount:</span> <b style="color: #38bdf8;">₹{alert_info.get('amount', 0):,.0f}</b></div>
                        <div><span style="color: #94a3b8;">Latitude:</span> <span class="coord-tag">{lat_formatted}</span></div>
                        <div><span style="color: #94a3b8;">Longitude:</span> <span class="coord-tag">{lon_formatted}</span></div>
                    </div>
                    
                    <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                        <a href="{google_maps_url}" target="_blank" class="map-btn-link" style="padding: 10px 20px; font-size: 14px;">
                            📍 VIEW ATM LOCATION ON MAP
                        </a>
                        <span style="font-size: 12px; color: #94a3b8;">
                            Opens exact coordinates ({lat_formatted}, {lon_formatted}) in Google Maps
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with r_card_right:
            st.markdown("#### Police Notification Action")
            st.info("The alert notification is automatically generated and sent to the configured police email.")

            if st.button("🚨 SEND POLICE ALERT", type="primary", use_container_width=True):
                with st.spinner("Dispatching police notification..."):
                    dispatch_res = send_fraud_alert_email(alert_info)
                    st.session_state.last_email_record = dispatch_res
                    st.success("Police alert email dispatched successfully!")
                    st.rerun()

            st.link_button("🌐 Open in Google Maps", google_maps_url, use_container_width=True)
            st.link_button("🗺️ Open in OpenStreetMap", osm_url, use_container_width=True)

        # ---------------------------------------------------------------------
        # POLICE EMAIL ALERT (Section 4 & 5)
        # -------------------------------------------------------------------------
        st.markdown("---")
        st.markdown("### 📧 Police Email Notification")
        email_rec = st.session_state.last_email_record

        if email_rec:
            st.success(f"✅ Notification Status: **{email_rec.get('status', 'Demo Email Generated Successfully')}**")
            email_cols = st.columns([6, 4])

            with email_cols[0]:
                st.markdown("#### Email Preview Received by Police")
                plain_body = format_alert_email_text(alert_info)
                st.markdown(
                    f"""
                    <div class="email-preview-card">
                        <div style="border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 12px;">
                            <div><b>Subject:</b> <span style="color: #f87171;">{DEFAULT_ALERT_SUBJECT}</span></div>
                            <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">
                                <b>To:</b> {email_rec.get('recipient', 'police.cybercell.demo@telangana.gov.in')} &nbsp;|&nbsp; 
                                <b>Time:</b> {email_rec.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}
                            </div>
                        </div>
                        <div style="white-space: pre-wrap; font-family: -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.6; font-size: 13px;">{plain_body}</div>
                        
                        <div style="margin-top: 18px; text-align: center;">
                            <a href="{google_maps_url}" target="_blank" class="map-btn-link" style="padding: 12px 24px; font-size: 14px;">
                                📍 CLICK TO VIEW ATM LOCATION ON GOOGLE MAPS
                            </a>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with email_cols[1]:
                st.markdown("#### 📍 Live ATM Location Display")
                st.markdown(
                    f"""
                    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #334155; border-radius: 8px; padding: 14px; margin-bottom: 12px; font-size: 13px;">
                        <div style="color: #38bdf8; font-weight: 700; margin-bottom: 4px;">📍 ATM LOCATION</div>
                        <div><b>Latitude:</b> <span class="coord-tag">{lat_formatted}</span></div>
                        <div><b>Longitude:</b> <span class="coord-tag">{lon_formatted}</span></div>
                        <div style="margin-top: 8px;">
                            <a href="{google_maps_url}" target="_blank" class="map-btn-link" style="font-size: 12px; padding: 6px 12px;">
                                🌐 OPEN MAP
                            </a>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Embedded mini focus map centered on ATM
                f_map = folium.Map(location=[atm_lat, atm_lon], zoom_start=15, tiles="OpenStreetMap")
                folium.Marker(
                    location=[atm_lat, atm_lon],
                    popup=f"<b>{alert_info.get('atm_id')}</b><br>{alert_info.get('area')}",
                    tooltip=f"{alert_info.get('atm_id')} ({alert_info.get('area')})",
                    icon=folium.Icon(color="red", icon="warning-sign"),
                ).add_to(f_map)
                folium.Circle(
                    location=[atm_lat, atm_lon],
                    radius=400,
                    color="#ef4444",
                    fill=True,
                    fill_opacity=0.15,
                ).add_to(f_map)
                st_folium(f_map, width=None, height=280, returned_objects=[])

# =============================================================================
# TAB 2: 🚔 POLICE ALERT DASHBOARD (SECTION 7, 8, 9)
# =============================================================================
with tabs[1]:
    st.markdown("### 🚔 Police Alert Command Dashboard")
    st.caption("Centralized operational queue for law enforcement officers to review alerts, open locations, and inspect evidence.")

    # 4 Top KPI Cards (Section 7)
    stats = get_alert_statistics()
    all_alerts = get_all_alerts(limit=50)

    # Unique ATM locations affected
    unique_atms_count = len(set(a.get("atm_id") for a in all_alerts)) if all_alerts else 0
    notifications_count = len(get_notification_logs(50))

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f"""
            <div class="kpi-card-box" style="border-color: rgba(239, 68, 68, 0.4);">
                <div class="kpi-card-title" style="color: #f87171;">🚨 NEW ALERTS</div>
                <div class="kpi-card-value" style="color: #ef4444;">{stats['new_alerts']}</div>
                <div class="kpi-card-sub">Pending Review</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"""
            <div class="kpi-card-box">
                <div class="kpi-card-title">📍 ATM LOCATIONS</div>
                <div class="kpi-card-value">{unique_atms_count}</div>
                <div class="kpi-card-sub">Affected Kiosks</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""
            <div class="kpi-card-box">
                <div class="kpi-card-title">🎥 EVIDENCE</div>
                <div class="kpi-card-value">{stats['evidence_analyzed']}</div>
                <div class="kpi-card-sub">Photos & Videos</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f"""
            <div class="kpi-card-box">
                <div class="kpi-card-title">📧 EMAIL ALERTS</div>
                <div class="kpi-card-value">{notifications_count}</div>
                <div class="kpi-card-sub">Notifications Sent</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # Filter by Status
    filter_choice = st.radio("Filter Alerts by Status:", ["All Alerts", "New Alerts", "Reviewed Alerts"], horizontal=True)
    if filter_choice == "New Alerts":
        display_alerts = [a for a in all_alerts if a.get("status") == "New"]
    elif filter_choice == "Reviewed Alerts":
        display_alerts = [a for a in all_alerts if a.get("status") in ["Acknowledged", "Reviewed", "Resolved"]]
    else:
        display_alerts = all_alerts

    st.markdown(f"#### Incident Queue ({len(display_alerts)} alerts)")

    if not display_alerts:
        st.info("No incident alerts matching the selected filter.")
    else:
        for idx, a in enumerate(display_alerts):
            a_lat = float(a.get("latitude", 17.4486))
            a_lon = float(a.get("longitude", 78.3908))
            a_lat_str = f"{a_lat:.6f}"
            a_lon_str = f"{a_lon:.6f}"
            a_map_url = generate_google_maps_link(a_lat, a_lon)
            is_new = a.get("status") == "New"
            status_badge_color = "#ef4444" if is_new else "#10b981"

            # Alert Card (Section 8)
            st.markdown(
                f"""
                <div class="police-alert-card">
                    <div class="police-alert-title">
                        <span>🚨 POTENTIAL FRAUD ALERT — {a.get('alert_id')}</span>
                        <span style="background: rgba(239, 68, 68, 0.15); color: {status_badge_color}; border: 1px solid {status_badge_color}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                            Status: {a.get('status', 'NEW').upper()}
                        </span>
                    </div>
                    
                    <div class="police-alert-grid">
                        <div class="police-alert-item">ATM: <b>{a.get('atm_id')} ({a.get('atm_name', 'Kiosk')})</b></div>
                        <div class="police-alert-item">Area: <b>{a.get('area', 'Hyderabad')}</b></div>
                        <div class="police-alert-item">Evidence: <b>{a.get('evidence_type', 'Image')}</b></div>
                        <div class="police-alert-item">Detection Time: <b>{a.get('timestamp')}</b></div>
                        <div class="police-alert-item">Latitude: <span class="coord-tag">{a_lat_str}</span></div>
                        <div class="police-alert-item">Longitude: <span class="coord-tag">{a_lon_str}</span></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 3 Action Buttons: [VIEW EVIDENCE], [VIEW LOCATION], [MARK AS REVIEWED] (Section 8)
            b1, b2, b3, b4 = st.columns([2.5, 3, 2.5, 4])
            with b1:
                # View Evidence Expander toggle
                toggle_key = f"view_ev_{a.get('alert_id')}_{idx}"
                show_ev = st.checkbox("🔍 VIEW EVIDENCE", key=toggle_key)
            with b2:
                # View Location (Opens Google Maps link)
                st.link_button("📍 VIEW LOCATION", a_map_url, use_container_width=True)
            with b3:
                # Mark as Reviewed
                if is_new:
                    if st.button("✅ MARK AS REVIEWED", key=f"mark_rev_{a.get('alert_id')}_{idx}", use_container_width=True):
                        mark_alert_reviewed(a["alert_id"], reviewer_name="Duty Officer")
                        st.success(f"Alert {a['alert_id']} marked as Reviewed.")
                        st.rerun()
                else:
                    st.caption(f"Reviewed by: {a.get('reviewed_by', 'Officer')}")

            # Inline Evidence Viewer
            if show_ev:
                ev_p = a.get("evidence_path", "")
                if ev_p and os.path.exists(ev_p):
                    _, ev_ext = os.path.splitext(ev_p)
                    st.markdown(f"**Evidence File:** `{os.path.basename(ev_p)}` (ID: `{a.get('evidence_id')}`)")
                    if ev_ext.lower() in [".mp4", ".avi", ".mov"]:
                        st.video(ev_p)
                    else:
                        st.image(ev_p, width=500)
                else:
                    st.info(f"Associated Evidence ID: {a.get('evidence_id')} (Synthetic Demo Sample)")

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# =============================================================================
# TAB 3: 📍 HOTSPOT & PATROL ANALYTICS (SECTION 14)
# =============================================================================
with tabs[2]:
    st.markdown("### 📍 Geospatial Hotspots & Patrol Coverage Analytics")
    st.caption("DBSCAN spatial clustering (Haversine metric) and heuristic patrol route recommendation supporting the alert response.")

    h_map_col, h_info_col = st.columns([7, 3])

    with h_map_col:
        st.markdown("#### Metropolitan Hotspot & Patrol Map")
        map_c1, map_c2, map_c3 = st.columns(3)
        with map_c1:
            show_pts = st.checkbox("Show ATM Points", value=True)
        with map_c2:
            show_hotspots = st.checkbox("Show Hotspot Clusters", value=True)
        with map_c3:
            show_route = st.checkbox("Show Patrol Circuit", value=True)

        hotspot_map = create_folium_dashboard_map(
            clean_df,
            cluster_stats_df=ranked_hotspots_df,
            patrol_route=default_patrol_route,
            show_raw_points=show_pts,
            show_centroids=show_hotspots,
            show_radii=show_hotspots,
            show_heatmap=False,
            show_patrol_route=show_route,
        )
        st_folium(hotspot_map, width=None, height=500, returned_objects=[])

    with h_info_col:
        st.markdown("#### Patrol Schedule")
        st.metric("Route Circuit", f"{default_patrol_route['total_distance_km']} km")
        st.metric("Estimated Time", default_patrol_route["estimated_travel_time"]["formatted_time"])
        st.metric("Hotspots Covered", f"{len(default_patrol_route['stops']) - 2} Clusters")

        st.markdown("---")
        st.markdown("#### Priority Hotspots")
        if not ranked_hotspots_df.empty:
            for _, h_row in ranked_hotspots_df.head(4).iterrows():
                st.markdown(
                    f"""
                    <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid #334155; border-radius: 6px; padding: 10px; margin-bottom: 8px; font-size: 12px;">
                        <b>#{int(h_row['ranking'])} {h_row['cluster_label']}: {h_row['primary_area']}</b><br>
                        • Volume: {int(h_row['num_withdrawals']):,} txns (₹{float(h_row['total_withdrawal_amount'])/1e5:.1f} Lakhs)<br>
                        • Priority: <b>{h_row['priority_tier']}</b> ({h_row['priority_score']} pts)
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No valid hotspot data is available yet.")

# =============================================================================
# TAB 4: 📑 REPORTS & AUDIT TRAIL
# =============================================================================
with tabs[3]:
    st.markdown("### 📑 Law Enforcement Incident & Audit Reports")
    st.caption("Export standardized reports for investigative case files and supervisory review.")

    rep1, rep2, rep3 = st.columns(3)

    with rep1:
        st.markdown("#### 📋 Incident Dossier Report")
        inc_df = generate_incident_report_df()
        if not inc_df.empty:
            csv_inc = inc_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Incident Report (CSV)", csv_inc, "incident_dossier_report.csv", "text/csv", use_container_width=True)
            st.dataframe(inc_df.head(5), use_container_width=True, hide_index=True)

    with rep2:
        st.markdown("#### 🚨 Police Alert Audit Log")
        alt_df = generate_alert_report_df()
        if not alt_df.empty:
            csv_alt = alt_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Alert Log (CSV)", csv_alt, "alert_audit_log.csv", "text/csv", use_container_width=True)
            st.dataframe(alt_df.head(5), use_container_width=True, hide_index=True)

    with rep3:
        st.markdown("#### 🎥 Digital Evidence Inventory")
        ev_df = generate_evidence_report_df()
        if not ev_df.empty:
            csv_ev = ev_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Evidence Log (CSV)", csv_ev, "evidence_inventory_log.csv", "text/csv", use_container_width=True)
            st.dataframe(ev_df.head(5), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# FOOTER
# -----------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; font-size: 11px; color: #64748b; padding: 10px 0;">
        FraudLocate Lite | Problem Statement PS-024 — Data Science & Predictive Analytics | Academic Demonstration System
    </div>
    """,
    unsafe_allow_html=True,
)
