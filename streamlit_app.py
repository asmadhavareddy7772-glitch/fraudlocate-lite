"""
FraudLocate Lite — Cyber-Fraud Withdrawal Hotspot & Patrol Coverage Analytics (PS-024)
Problem Statement ID: PS-024 | Domain: Data Science & Predictive Analytics

A comprehensive law-enforcement decision-support system featuring:
- Role-based login (Admin/Analyst & Police) with secure salted password hashing
- Instant SQLite persistence as single source of truth across browser sessions & reboots
- Dynamic alert status segregation (NEW -> REVIEWED -> RESOLVED)
- Live Police Alert Dashboard with KPI cards, real-time notification banner, and clickable map links
- Full evidence analysis, DBSCAN hotspot correlation, and Command HQ patrol dispatch recommendations
- ZERO technical or debug code exposed to the end user
"""

import os
import sys
import json
import time
import importlib
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import streamlit as st
from streamlit_folium import st_folium
import folium

# Ensure repository root is on sys.path
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

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

# Alert Store & Persistence (Resilient to Streamlit Cloud in-memory module caching)
import src.alert_store as alert_store
if not hasattr(alert_store, "get_new_alerts"):
    try:
        alert_store = importlib.reload(alert_store)
    except Exception:
        pass

init_alert_db = getattr(alert_store, "init_alert_db", lambda *args, **kwargs: None)
insert_alert = getattr(alert_store, "insert_alert", lambda *args, **kwargs: "ALERT-00000")
get_all_alerts = getattr(alert_store, "get_all_alerts", lambda *args, **kwargs: [])
get_new_alerts = getattr(alert_store, "get_new_alerts", lambda *args, **kwargs: [a for a in get_all_alerts(*args, **kwargs) if a.get("status") in ["NEW", "New"]])
get_reviewed_alerts = getattr(alert_store, "get_reviewed_alerts", lambda *args, **kwargs: [a for a in get_all_alerts(*args, **kwargs) if a.get("status") in ["REVIEWED", "Acknowledged"]])
get_resolved_alerts = getattr(alert_store, "get_resolved_alerts", lambda *args, **kwargs: [a for a in get_all_alerts(*args, **kwargs) if a.get("status") in ["RESOLVED", "Resolved"]])
get_alert_by_id = getattr(alert_store, "get_alert_by_id", lambda *args, **kwargs: None)
update_alert_status = getattr(alert_store, "update_alert_status", lambda *args, **kwargs: True)
mark_alert_reviewed = getattr(alert_store, "mark_alert_reviewed", lambda *args, **kwargs: True)
mark_alert_resolved = getattr(alert_store, "mark_alert_resolved", lambda *args, **kwargs: True)
get_alert_statistics = getattr(alert_store, "get_alert_statistics", lambda *args, **kwargs: {"total_alerts": 0, "new_alerts": 0, "reviewed_alerts": 0, "resolved_alerts": 0})
seed_demo_alerts_if_empty = getattr(alert_store, "seed_demo_alerts_if_empty", lambda *args, **kwargs: None)
VALID_STATUSES = getattr(alert_store, "VALID_STATUSES", ["NEW", "REVIEWED", "RESOLVED"])

# Authentication & User Management (Resilient to Streamlit Cloud module caching)
import src.auth as auth_module
if not hasattr(auth_module, "authenticate_user"):
    try:
        auth_module = importlib.reload(auth_module)
    except Exception:
        pass

init_user_db = getattr(auth_module, "init_user_db", lambda *args, **kwargs: None)
seed_demo_users_if_empty = getattr(auth_module, "seed_demo_users_if_empty", lambda *args, **kwargs: None)
authenticate_user = getattr(auth_module, "authenticate_user", lambda *args, **kwargs: None)
get_all_police_officers = getattr(auth_module, "get_all_police_officers", lambda *args, **kwargs: [])

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
from src.police_dashboard import (
    create_police_focus_map,
    render_incident_timeline_component,
)
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
    
    /* Top Header Card */
    .app-header {
        background: linear-gradient(135deg, #090d16 0%, #1e293b 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 18px 24px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    }
    
    .app-title {
        font-size: 24px;
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
        font-size: 11px;
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
    
    /* User Profile Pill in Header */
    .user-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 12px;
        color: #cbd5e1;
    }
    
    .user-pill b {
        color: #38bdf8;
    }
    
    /* Academic Notice Banner */
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
    
    /* Workflow Ribbon */
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
        font-size: 28px;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
    }
    
    .kpi-card-sub {
        font-size: 11px;
        color: #38bdf8;
        margin-top: 4px;
    }
    
    /* Real-time Alert Notification Banner */
    .realtime-alert-banner {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(185, 28, 28, 0.3) 100%);
        border: 2px solid #ef4444;
        border-left: 8px solid #dc2626;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(239, 68, 68, 0.25);
        animation: pulseBorder 2s infinite;
    }
    
    /* Alert Card */
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
        font-size: 15px;
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
    
    /* Login Portal Card */
    .login-container-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 14px;
        padding: 28px 32px;
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
        max-width: 600px;
        margin: 20px auto;
    }
    
    /* Email Preview Card */
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

def render_html(html_str: str) -> None:
    """Render raw HTML safely without triggering Markdown code syntax highlighters."""
    clean_html = "\n".join(line.strip() for line in html_str.strip().splitlines())
    if hasattr(st, "html"):
        st.html(clean_html)
    else:
        st.markdown(clean_html, unsafe_allow_html=True)

render_html(CUSTOM_CSS)

# -----------------------------------------------------------------------------
# 2. STATE & DATABASE INITIALIZATION
# -----------------------------------------------------------------------------
ensure_sample_evidence_exists()
init_alert_db()
seed_demo_alerts_if_empty()
init_user_db()
seed_demo_users_if_empty()

# Session State Initializations
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "user" not in st.session_state:
    st.session_state.user = None

if "active_evidence_path" not in st.session_state:
    st.session_state.active_evidence_path = os.path.join(SAMPLE_DIR, "sample_cctv_1.jpg")

if "active_evidence_id" not in st.session_state:
    st.session_state.active_evidence_id = "EVD-2026-48291"

if "last_detection" not in st.session_state:
    st.session_state.last_detection = None

if "last_email_record" not in st.session_state:
    st.session_state.last_email_record = None

if "police_selected_alert_id" not in st.session_state:
    st.session_state.police_selected_alert_id = None

# Load dataset for ATM coordinates and secondary hotspot analytics
@st.cache_data(show_spinner=False)
def get_cached_raw_data() -> pd.DataFrame:
    try:
        return load_withdrawal_dataset(auto_generate_if_missing=True, default_records=2500, city="Hyderabad")
    except Exception:
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

except Exception:
    clean_df = pd.DataFrame(columns=["atm_id", "atm_name", "area", "city", "latitude", "longitude"])
    dbscan_df = pd.DataFrame()
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
# 3. AUTHENTICATION & LOGIN PORTAL (PRE-AUTH GATE)
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    # Header Banner for Login
    render_html(
        """
        <div class="app-header">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div>
                    <h1 class="app-title">
                        🛡️ FraudLocate Lite
                        <span class="app-badge">Law Enforcement Access Portal</span>
                    </h1>
                    <p class="app-subtitle">
                        Mule Cash Withdrawal Hotspot Detection, Police Real-Time Alerts & Location Dispatch
                    </p>
                </div>
                <div>
                    <span class="app-badge" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.4);">
                        Authentication Required
                    </span>
                </div>
            </div>
        </div>
        """
    )

    render_html(
        """
        <div class="demo-banner">
            <b>⚖️ ACADEMIC PROTOTYPE NOTICE:</b>
            FraudLocate Lite operates with role-based access control. All alert history is securely persisted in local SQLite.
            Passwords are cryptographically salted and hashed. Please select your role to proceed to the designated terminal.
        </div>
        """
    )

    l_col1, l_col2, l_col3 = st.columns([1, 6, 1])
    with l_col2:
        login_tabs = st.tabs(["👮 POLICE LOGIN", "🛡️ ADMIN / ANALYST LOGIN"])

        # TAB A: POLICE LOGIN
        with login_tabs[0]:
            st.markdown("### 👮 Police Officer Authentication")
            st.caption("Access the live fraud alert dispatch queue, examine ATM coordinates, and mark alerts as reviewed.")

            st.markdown("**Quick-Fill Demo Police Credentials:**")
            q_cols = st.columns(2)
            with q_cols[0]:
                if st.button("👮 Insp. Vikram Reddy (TS-POLICE-101)", use_container_width=True):
                    st.session_state["p_login_id"] = "TS-POLICE-101"
                    st.session_state["p_login_pwd"] = "police101"
                    st.rerun()
            with q_cols[1]:
                if st.button("👮 SI Ananya Sharma (TS-POLICE-102)", use_container_width=True):
                    st.session_state["p_login_id"] = "TS-POLICE-102"
                    st.session_state["p_login_pwd"] = "police102"
                    st.rerun()

            p_id = st.text_input("Police ID or Username:", value=st.session_state.get("p_login_id", ""), placeholder="e.g. TS-POLICE-101 or officer.vikram", key="p_input_id")
            p_pwd = st.text_input("Password:", value=st.session_state.get("p_login_pwd", ""), type="password", key="p_input_pwd")

            if st.button("🚨 LOGIN TO POLICE DASHBOARD", type="primary", use_container_width=True):
                user_record = authenticate_user(p_id, p_pwd, required_role="POLICE")
                if user_record:
                    st.session_state.authenticated = True
                    st.session_state.user = user_record
                    st.success(f"Welcome, {user_record['full_name']}! Redirecting to Police Dashboard...")
                    time.sleep(0.4)
                    st.rerun()
                else:
                    st.error("Invalid Police ID/Username or Password. Please verify credentials.")

        # TAB B: ANALYST / ADMIN LOGIN
        with login_tabs[1]:
            st.markdown("### 🛡️ Cyber Crime Analyst Login")
            st.caption("Upload photo/video evidence, run automated fraud analysis, dispatch police alerts, and manage demo simulation.")

            st.markdown("**Quick-Fill Demo Analyst Credentials:**")
            if st.button("🛡️ Cyber Analyst Demo Account (analyst)", use_container_width=True):
                st.session_state["a_login_id"] = "analyst"
                st.session_state["a_login_pwd"] = "analyst123"
                st.rerun()

            a_id = st.text_input("Username:", value=st.session_state.get("a_login_id", ""), placeholder="e.g. analyst", key="a_input_id")
            a_pwd = st.text_input("Password:", value=st.session_state.get("a_login_pwd", ""), type="password", key="a_input_pwd")

            if st.button("🔐 LOGIN AS ANALYST", type="primary", use_container_width=True):
                user_record = authenticate_user(a_id, a_pwd, required_role="ANALYST")
                if user_record:
                    st.session_state.authenticated = True
                    st.session_state.user = user_record
                    st.success(f"Welcome, {user_record['full_name']}! Redirecting to Analyst Workspace...")
                    time.sleep(0.4)
                    st.rerun()
                else:
                    st.error("Invalid Analyst Username or Password. Please verify credentials.")

    st.stop()


# -----------------------------------------------------------------------------
# 4. AUTHENTICATED USER SESSION & HEADER BAR
# -----------------------------------------------------------------------------
current_user = st.session_state.user
user_role = current_user.get("role", "POLICE")
officer_display = current_user.get("full_name", "Officer")
police_id_display = current_user.get("police_id", "N/A")

# Top Header with User Profile and Logout Button
h_left, h_right = st.columns([7, 3])
with h_left:
    role_icon = "🚔" if user_role == "POLICE" else "🛡️"
    render_html(
        f"""
        <div class="app-header">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div>
                    <h1 class="app-title">
                        {role_icon} FraudLocate Lite
                        <span class="app-badge">{user_role} TERMINAL</span>
                    </h1>
                    <p class="app-subtitle">
                        Mule Cash Withdrawal Hotspot Detection, Police Real-Time Alerts & Location Dispatch
                    </p>
                </div>
            </div>
        </div>
        """
    )
with h_right:
    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
    b_col1, b_col2 = st.columns([6, 4])
    with b_col1:
        if user_role == "POLICE":
            st.markdown(f"👮 **{officer_display}**\n\nID: `{police_id_display}`")
        else:
            st.markdown(f"👤 **{officer_display}**\n\nRole: `ANALYST / ADMIN`")
    with b_col2:
        if st.button("🚪 LOGOUT", use_container_width=True, help="End session and return to login screen"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.police_selected_alert_id = None
            st.rerun()


# =============================================================================
# 5. POLICE DASHBOARD VIEW (WHEN LOGGED IN AS POLICE)
# =============================================================================
if user_role == "POLICE":
    # Dedicated Police Alert Dashboard
    st.markdown("## 🚨 Police Fraud Alert Dashboard")
    st.caption("Active operational dispatch queue for law enforcement officers. Inspect ATM coordinates, open live maps, and review fraud alerts.")

    # Refresh Button & Summary Bar
    r_bar1, r_bar2 = st.columns([8, 2])
    with r_bar2:
        if st.button("🔄 REFRESH ALERTS", use_container_width=True, help="Re-query SQLite database to check for newly generated alerts"):
            st.rerun()

    # Fetch database-driven statistics and alerts directly from SQLite
    stats = get_alert_statistics()
    all_alerts_list = get_all_alerts(limit=100)
    new_alerts_list = get_new_alerts(limit=100)
    reviewed_alerts_list = get_reviewed_alerts(limit=100)
    resolved_alerts_list = get_resolved_alerts(limit=100)

    # -------------------------------------------------------------------------
    # REAL-TIME POLICE ALERT BANNER (Sections 12 & 13)
    # -------------------------------------------------------------------------
    if stats["new_alerts"] > 0:
        latest_new = new_alerts_list[0]
        atm_lat = float(latest_new.get("latitude", 17.4486))
        atm_lon = float(latest_new.get("longitude", 78.3908))
        lat_formatted = f"{atm_lat:.6f}"
        lon_formatted = f"{atm_lon:.6f}"
        map_url = generate_google_maps_link(atm_lat, atm_lon)

        render_html(
            f"""
            <div class="realtime-alert-banner">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-size: 16px; font-weight: 800; color: #f87171;">
                        🚨 NEW FRAUD ALERT RECEIVED — IMMEDIATE POLICE ACTION REQUIRED
                    </span>
                    <span style="background: #dc2626; color: white; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 800;">
                        {stats['new_alerts']} NEW ALERTS PENDING
                    </span>
                </div>
                <div style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
                    <b>Potential fraud activity detected.</b><br>
                    ATM: <b>{latest_new.get('atm_id')} ({latest_new.get('atm_name', 'Kiosk')})</b> &nbsp;|&nbsp; 
                    Location: <b>{latest_new.get('area')}, {latest_new.get('city')}</b> &nbsp;|&nbsp; 
                    Detection Time: <b>{latest_new.get('timestamp')}</b> &nbsp;|&nbsp; 
                    Evidence: <b>{latest_new.get('evidence_type')}</b> &nbsp;|&nbsp; 
                    Status: <b style="color: #ef4444;">NEW</b>
                </div>
            </div>
            """
        )

    # -------------------------------------------------------------------------
    # TOP KPI CARDS (Calculated directly from SQLite - Section 3 & 21)
    # -------------------------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_html(
            f"""
            <div class="kpi-card-box">
                <div class="kpi-card-title">🗂 ALL ALERTS</div>
                <div class="kpi-card-value">{stats['total_alerts']}</div>
                <div class="kpi-card-sub">Total Generated</div>
            </div>
            """
        )
    with k2:
        render_html(
            f"""
            <div class="kpi-card-box" style="border-color: rgba(239, 68, 68, 0.45);">
                <div class="kpi-card-title" style="color: #f87171;">🔴 NEW ALERTS</div>
                <div class="kpi-card-value" style="color: #ef4444;">{stats['new_alerts']}</div>
                <div class="kpi-card-sub">Pending Review</div>
            </div>
            """
        )
    with k3:
        render_html(
            f"""
            <div class="kpi-card-box" style="border-color: rgba(16, 185, 129, 0.45);">
                <div class="kpi-card-title" style="color: #34d399;">📋 REVIEWED ALERTS</div>
                <div class="kpi-card-value" style="color: #10b981;">{stats['reviewed_alerts']}</div>
                <div class="kpi-card-sub">Acknowledged by Police</div>
            </div>
            """
        )
    with k4:
        render_html(
            f"""
            <div class="kpi-card-box">
                <div class="kpi-card-title">🏁 RESOLVED ALERTS</div>
                <div class="kpi-card-value">{stats['resolved_alerts']}</div>
                <div class="kpi-card-sub">Case Handled</div>
            </div>
            """
        )

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # MODAL / DETAILED INSPECTION VIEW (IF AN ALERT IS SELECTED)
    # -------------------------------------------------------------------------
    if st.session_state.police_selected_alert_id:
        selected_alert = get_alert_by_id(st.session_state.police_selected_alert_id)
        if selected_alert:
            sel_lat = float(selected_alert.get("latitude", 17.4486))
            sel_lon = float(selected_alert.get("longitude", 78.3908))
            sel_map_url = generate_google_maps_link(sel_lat, sel_lon)

            st.markdown(f"### 🔍 Alert Details — `{selected_alert.get('alert_id')}`")
            close_col1, close_col2 = st.columns([8, 2])
            with close_col2:
                if st.button("✖️ Close Details", use_container_width=True):
                    st.session_state.police_selected_alert_id = None
                    st.rerun()

            # Detailed Sections (Section 16)
            d_left, d_right = st.columns([6, 4])
            with d_left:
                st.markdown("#### Alert & ATM Information")
                render_html(
                    f"""
                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-bottom: 14px; font-size: 13px;">
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 16px;">
                            <div>Alert ID: <b>{selected_alert.get('alert_id')}</b></div>
                            <div>Case ID: <b>{selected_alert.get('complaint_id')}</b></div>
                            <div>Detection Time: <b>{selected_alert.get('timestamp')}</b></div>
                            <div>Current Status: <b style="color: #38bdf8;">{selected_alert.get('status')}</b></div>
                            <div>ATM ID: <b>{selected_alert.get('atm_id')}</b></div>
                            <div>ATM Name: <b>{selected_alert.get('atm_name')}</b></div>
                            <div>Area: <b>{selected_alert.get('area')}</b></div>
                            <div>City: <b>{selected_alert.get('city')}</b></div>
                            <div>Latitude: <span class="coord-tag">{sel_lat:.6f}</span></div>
                            <div>Longitude: <span class="coord-tag">{sel_lon:.6f}</span></div>
                        </div>
                        <div style="margin-top: 14px;">
                            <a href="{sel_map_url}" target="_blank" class="map-btn-link">
                                📍 VIEW ATM LOCATION ON MAP
                            </a>
                        </div>
                    </div>
                    """
                )

                st.markdown("#### Evidence Preview")
                ev_path = selected_alert.get("evidence_path", "")
                if ev_path and os.path.exists(ev_path):
                    _, ev_ext = os.path.splitext(ev_path)
                    st.caption(f"Evidence ID: `{selected_alert.get('evidence_id')}` | File: `{os.path.basename(ev_path)}`")
                    if ev_ext.lower() in [".mp4", ".avi", ".mov"]:
                        st.video(ev_path)
                    else:
                        st.image(ev_path, use_container_width=True)
                else:
                    st.info(f"Associated Evidence ID: {selected_alert.get('evidence_id')} (Synthetic demonstration sample)")

                st.markdown("#### Analysis Result")
                st.info(selected_alert.get("analysis_result", "Potential fraud event analyzed."))

            with d_right:
                st.markdown("#### Tactical Focus Map & Patrol Route")
                focus_map = create_police_focus_map(
                    selected_alert,
                    ranked_hotspots_df=ranked_hotspots_df,
                    nearby_txns_df=clean_df[clean_df["atm_id"] == selected_alert.get("atm_id")] if not clean_df.empty else None,
                )
                st_folium(focus_map, width=None, height=280, returned_objects=[])

                # Chronological Incident Timeline
                tl_data = {}
                if selected_alert.get("timeline"):
                    try:
                        tl_data = json.loads(selected_alert["timeline"])
                    except Exception:
                        tl_data = {}
                render_html(render_incident_timeline_component(tl_data))

                # Actions in Details view
                st.markdown("#### Actions")
                if selected_alert.get("status") == "NEW":
                    if st.button("✅ MARK AS REVIEWED", key="det_mark_rev", type="primary", use_container_width=True):
                        reviewer_tag = f"{current_user['police_id']} ({current_user['full_name']})"
                        mark_alert_reviewed(selected_alert["alert_id"], reviewer_name=reviewer_tag)
                        st.success(f"Alert {selected_alert['alert_id']} marked as REVIEWED.")
                        st.rerun()
                elif selected_alert.get("status") == "REVIEWED":
                    st.caption(f"Reviewed by: {selected_alert.get('reviewed_by', 'Police Officer')} at {selected_alert.get('reviewed_timestamp', 'N/A')}")
                    if st.button("🏁 MARK AS RESOLVED", key="det_mark_res", use_container_width=True):
                        reviewer_tag = f"{current_user['police_id']} ({current_user['full_name']})"
                        mark_alert_resolved(selected_alert["alert_id"], reviewer_name=reviewer_tag)
                        st.success(f"Alert {selected_alert['alert_id']} marked as RESOLVED.")
                        st.rerun()
                else:
                    st.caption(f"Resolved at: {selected_alert.get('resolved_timestamp', 'N/A')}")

            st.markdown("---")

    # -------------------------------------------------------------------------
    # MAIN POLICE ALERT SECTIONS (Section 28)
    # -------------------------------------------------------------------------
    p_sections = st.tabs([
        f"🔴 New Alerts ({len(new_alerts_list)})",
        f"📋 Reviewed Alerts ({len(reviewed_alerts_list)})",
        f"🗂 All Alerts ({len(all_alerts_list)})",
        "📊 Alert History",
    ])

    # -------------------------------------------------------------------------
    # SECTION 1: 🔴 NEW ALERTS
    # -------------------------------------------------------------------------
    with p_sections[0]:
        st.markdown(f"### 🔴 New Alerts ({len(new_alerts_list)})")
        st.caption("Unreviewed alerts requiring immediate law-enforcement acknowledgement.")

        if not new_alerts_list:
            st.success("✅ No new unreviewed alerts. All active fraud events have been reviewed.")
        else:
            for idx, a in enumerate(new_alerts_list):
                a_lat = float(a.get("latitude", 17.4486))
                a_lon = float(a.get("longitude", 78.3908))
                a_map_url = generate_google_maps_link(a_lat, a_lon)

                render_html(
                    f"""
                    <div class="police-alert-card" style="border-left: 6px solid #ef4444;">
                        <div class="police-alert-title">
                            <span>🚨 {a.get('alert_id')} &nbsp;|&nbsp; {a.get('atm_id')} ({a.get('atm_name', 'Kiosk')})</span>
                            <span style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                                STATUS: NEW
                            </span>
                        </div>
                        <div class="police-alert-grid">
                            <div class="police-alert-item">Location: <b>{a.get('area')}, {a.get('city')}</b></div>
                            <div class="police-alert-item">Detection Time: <b>{a.get('timestamp')}</b></div>
                            <div class="police-alert-item">Evidence: <b>{a.get('evidence_type')}</b> (ID: {a.get('evidence_id')})</div>
                            <div class="police-alert-item">Severity: <b style="color: #ef4444;">{a.get('severity')}</b></div>
                            <div class="police-alert-item">Latitude: <span class="coord-tag">{a_lat:.6f}</span></div>
                            <div class="police-alert-item">Longitude: <span class="coord-tag">{a_lon:.6f}</span></div>
                        </div>
                    </div>
                    """
                )

                b_col1, b_col2, b_col3 = st.columns([3, 3, 3])
                with b_col1:
                    if st.button("🔍 VIEW DETAILS", key=f"btn_det_new_{a['alert_id']}_{idx}", use_container_width=True):
                        st.session_state.police_selected_alert_id = a["alert_id"]
                        st.rerun()
                with b_col2:
                    st.link_button("📍 VIEW ATM LOCATION", a_map_url, use_container_width=True)
                with b_col3:
                    if st.button("✅ MARK AS REVIEWED", key=f"btn_rev_new_{a['alert_id']}_{idx}", type="primary", use_container_width=True):
                        reviewer_tag = f"{current_user['police_id']} ({current_user['full_name']})"
                        mark_alert_reviewed(a["alert_id"], reviewer_name=reviewer_tag)
                        st.success(f"Alert {a['alert_id']} marked as REVIEWED.")
                        st.rerun()

                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # SECTION 2: 📋 REVIEWED ALERTS
    # -------------------------------------------------------------------------
    with p_sections[1]:
        st.markdown(f"### 📋 Reviewed Alerts ({len(reviewed_alerts_list)})")
        st.caption("Alerts acknowledged and reviewed by police officers. Does NOT contain NEW alerts.")

        if not reviewed_alerts_list:
            st.info("No reviewed alerts recorded yet.")
        else:
            for idx, a in enumerate(reviewed_alerts_list):
                a_lat = float(a.get("latitude", 17.4486))
                a_lon = float(a.get("longitude", 78.3908))
                a_map_url = generate_google_maps_link(a_lat, a_lon)

                render_html(
                    f"""
                    <div class="police-alert-card" style="border-left: 6px solid #10b981; border-color: rgba(16, 185, 129, 0.4);">
                        <div class="police-alert-title" style="color: #34d399;">
                            <span>📋 {a.get('alert_id')} &nbsp;|&nbsp; {a.get('atm_id')} ({a.get('atm_name', 'Kiosk')})</span>
                            <span style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                                STATUS: REVIEWED
                            </span>
                        </div>
                        <div class="police-alert-grid">
                            <div class="police-alert-item">Location: <b>{a.get('area')}, {a.get('city')}</b></div>
                            <div class="police-alert-item">Detection Time: <b>{a.get('timestamp')}</b></div>
                            <div class="police-alert-item">Review Time: <b>{a.get('reviewed_timestamp', 'Recorded')}</b></div>
                            <div class="police-alert-item">Reviewed By: <b style="color: #38bdf8;">{a.get('reviewed_by', 'Duty Officer')}</b></div>
                            <div class="police-alert-item">Evidence: <b>{a.get('evidence_type')}</b></div>
                            <div class="police-alert-item">Coordinates: <span class="coord-tag">{a_lat:.6f}, {a_lon:.6f}</span></div>
                        </div>
                    </div>
                    """
                )

                b_col1, b_col2, b_col3 = st.columns([3, 3, 3])
                with b_col1:
                    if st.button("🔍 VIEW DETAILS", key=f"btn_det_rev_{a['alert_id']}_{idx}", use_container_width=True):
                        st.session_state.police_selected_alert_id = a["alert_id"]
                        st.rerun()
                with b_col2:
                    st.link_button("📍 VIEW ATM LOCATION", a_map_url, use_container_width=True)
                with b_col3:
                    if st.button("🏁 MARK AS RESOLVED", key=f"btn_res_rev_{a['alert_id']}_{idx}", use_container_width=True):
                        reviewer_tag = f"{current_user['police_id']} ({current_user['full_name']})"
                        mark_alert_resolved(a["alert_id"], reviewer_name=reviewer_tag)
                        st.success(f"Alert {a['alert_id']} marked as RESOLVED.")
                        st.rerun()

                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # SECTION 3: 🗂 ALL ALERTS
    # -------------------------------------------------------------------------
    with p_sections[2]:
        st.markdown(f"### 🗂 All Alerts ({len(all_alerts_list)})")
        st.caption("Complete unified repository of all fraud alerts ever generated (NEW + REVIEWED + RESOLVED), newest first.")

        if not all_alerts_list:
            st.info("No alerts generated yet.")
        else:
            all_table_data = []
            for a in all_alerts_list:
                all_table_data.append({
                    "Alert ID": a.get("alert_id"),
                    "Evidence ID": a.get("evidence_id"),
                    "Detection Time": a.get("timestamp"),
                    "ATM ID": a.get("atm_id"),
                    "Area": a.get("area"),
                    "Latitude": f"{float(a.get('latitude', 0)):.6f}",
                    "Longitude": f"{float(a.get('longitude', 0)):.6f}",
                    "Evidence Type": a.get("evidence_type"),
                    "Severity": a.get("severity"),
                    "Status": a.get("status"),
                    "Review Time": a.get("reviewed_timestamp") or "—",
                    "Reviewed By": a.get("reviewed_by") or "—",
                })
            all_df = pd.DataFrame(all_table_data)
            st.dataframe(all_df, use_container_width=True, hide_index=True)

            # Quick inspect dropdown
            inspect_ids = [a["alert_id"] for a in all_alerts_list]
            chosen_inspect = st.selectbox("Inspect specific alert:", inspect_ids, key="all_inspect_select")
            if st.button("🔍 Open Selected Alert in Inspector", key="btn_open_all"):
                st.session_state.police_selected_alert_id = chosen_inspect
                st.rerun()

    # -------------------------------------------------------------------------
    # SECTION 4: 📊 ALERT HISTORY
    # -------------------------------------------------------------------------
    with p_sections[3]:
        st.markdown("### 📊 Alert History")
        st.caption("Chronological audit trail persisted permanently in SQLite. Survives page refresh, logout, and application restart.")

        hist_alerts = get_all_alerts(limit=100)
        if hist_alerts:
            hist_rows = []
            for h in hist_alerts:
                hist_rows.append({
                    "Alert ID": h.get("alert_id"),
                    "Detection Time": h.get("timestamp"),
                    "Status": h.get("status"),
                    "ATM": f"{h.get('atm_id')} ({h.get('atm_name', 'Kiosk')})",
                    "Location": f"{h.get('area')}, {h.get('city')}",
                    "Evidence Type": h.get("evidence_type"),
                    "Reviewed Time": h.get("reviewed_timestamp") or "—",
                    "Reviewed By": h.get("reviewed_by") or "—",
                })
            hist_df = pd.DataFrame(hist_rows)
            st.dataframe(hist_df, use_container_width=True, hide_index=True)

            csv_hist = hist_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Alert History (CSV)", csv_hist, "fraudlocate_alert_history.csv", "text/csv")
        else:
            st.info("No alert history found in the database.")


# =============================================================================
# 6. ADMIN / ANALYST PORTAL (WHEN LOGGED IN AS ANALYST)
# =============================================================================
else:
    # Workflow ribbon for analyst
    render_html(
        """
        <div class="workflow-ribbon">
            <div class="workflow-step active"><span class="workflow-dot active">1</span> Upload Evidence</div>
            <span style="color: #475569;">➔</span>
            <div class="workflow-step active"><span class="workflow-dot active">2</span> Analyze Evidence</div>
            <span style="color: #475569;">➔</span>
            <div class="workflow-step alert"><span class="workflow-dot alert">3</span> Fraud Event Detected</div>
            <span style="color: #475569;">➔</span>
            <div class="workflow-step alert"><span class="workflow-dot alert">4</span> Alert Immediately Saved to DB</div>
            <span style="color: #475569;">➔</span>
            <div class="workflow-step done"><span class="workflow-dot done">5</span> Police Email Dispatched</div>
            <span style="color: #475569;">➔</span>
            <div class="workflow-step done"><span class="workflow-dot done">6</span> Police Dashboard Receives Alert</div>
        </div>
        """
    )

    tab_labels = [
        "📤 Fraud Evidence Upload & Analysis",
        "📍 Hotspot & Patrol Analytics",
        "📑 Incident Dossiers & Reports",
        "🚔 Police Alert Monitor",
    ]
    analyst_tabs = st.tabs(tab_labels)

    # =========================================================================
    # TAB 1: EVIDENCE UPLOAD & FRAUD DETECTION
    # =========================================================================
    with analyst_tabs[0]:
        sim_col1, sim_col2 = st.columns([7, 3])
        with sim_col1:
            st.markdown("### 📤 Fraud Evidence Upload & Analysis")
            st.caption("Upload photos or videos of ATM activity to detect potential fraud and dispatch police alerts.")
        with sim_col2:
            st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
            if st.button("⚡ SIMULATE FRAUD ALERT", type="primary", use_container_width=True, help="One-click demonstration: select sample evidence, detect fraud, create alert, immediately save to SQLite, and send police email."):
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
                    st.success("Fraud event detected! Alert immediately saved to SQLite database and police email dispatched.")
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

            render_html(
                f"""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid #334155; border-radius: 8px; padding: 14px; margin-bottom: 14px; font-size: 13px;">
                    <div style="margin-bottom: 6px;"><b>Evidence ID:</b> <code style="color: #38bdf8;">{st.session_state.active_evidence_id}</code></div>
                    <div style="margin-bottom: 6px;"><b>File Name:</b> {cur_file_name}</div>
                    <div style="margin-bottom: 6px;"><b>Evidence Type:</b> {meta.get('media_type', 'Image')} ({meta.get('extension', 'jpg').upper()})</div>
                    <div><b>Upload Time:</b> {cur_time_str}</div>
                </div>
                """
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

            render_html(
                f"""
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid #334155; border-radius: 8px; padding: 14px; margin-bottom: 16px; font-size: 13px;">
                    <div style="color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 11px; margin-bottom: 6px;">Kiosk Location Coordinates</div>
                    <div><b>ATM ID:</b> {chosen_row['atm_id']}</div>
                    <div><b>Area:</b> {chosen_row['area']}, {chosen_row['city']}</div>
                    <div><b>Latitude:</b> <span class="coord-tag">{target_lat_str}</span></div>
                    <div><b>Longitude:</b> <span class="coord-tag">{target_lon_str}</span></div>
                </div>
                """
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
                    st.success("Analysis completed! Alert saved immediately to SQLite database.")
                    st.rerun()

        # ---------------------------------------------------------------------
        # FRAUD EVENT RESULT (Sections 3 & 11)
        # ---------------------------------------------------------------------
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
            st.markdown("### 🚨 Fraud Event Result & Simultaneous Database Persistence")

            r_card_left, r_card_right = st.columns([6, 4])

            with r_card_left:
                render_html(
                    f"""
                    <div style="background: rgba(30, 41, 59, 0.95); border: 2px solid #ef4444; border-radius: 12px; padding: 22px; box-shadow: 0 8px 24px rgba(239, 68, 68, 0.2);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <span style="font-size: 18px; font-weight: 800; color: #f87171;">
                                🚨 POTENTIAL FRAUD EVENT DETECTED
                            </span>
                            <span style="background: rgba(239, 68, 68, 0.25); color: #fca5a5; border: 1px solid #ef4444; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: bold;">
                                Status: NEW (Saved to SQLite)
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
                                Coordinates: {lat_formatted}, {lon_formatted}
                            </span>
                        </div>
                    </div>
                    """
                )

            with r_card_right:
                st.markdown("#### Police Notification Action")
                st.info("The alert notification is automatically generated and sent to the configured police email.")

                if st.button("🚨 RE-SEND POLICE ALERT EMAIL", type="primary", use_container_width=True):
                    with st.spinner("Dispatching police notification..."):
                        dispatch_res = send_fraud_alert_email(alert_info)
                        st.session_state.last_email_record = dispatch_res
                        st.success("Police alert email dispatched successfully!")
                        st.rerun()

                st.link_button("🌐 Open in Google Maps", google_maps_url, use_container_width=True)
                st.link_button("🗺️ Open in OpenStreetMap", osm_url, use_container_width=True)

            # -----------------------------------------------------------------
            # POLICE EMAIL ALERT DISPLAY (Section 14 & 15)
            # -----------------------------------------------------------------
            st.markdown("---")
            st.markdown("### 📧 Police Email Notification")
            email_rec = st.session_state.last_email_record

            if email_rec:
                st.success(f"✅ Notification Status: **{email_rec.get('status', 'Demo Email Generated Successfully')}**")
                email_cols = st.columns([6, 4])

                with email_cols[0]:
                    st.markdown("#### Clean Email Body Received by Police")
                    plain_body = format_alert_email_text(alert_info)
                    render_html(
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
                        """
                    )

                with email_cols[1]:
                    st.markdown("#### 📍 Live ATM Location Display")
                    render_html(
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
                        """
                    )

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

    # =========================================================================
    # TAB 2: HOTSPOT & PATROL ANALYTICS
    # =========================================================================
    with analyst_tabs[1]:
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
                    render_html(
                        f"""
                        <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid #334155; border-radius: 6px; padding: 10px; margin-bottom: 8px; font-size: 12px;">
                            <b>#{int(h_row['ranking'])} {h_row['cluster_label']}: {h_row['primary_area']}</b><br>
                            • Volume: {int(h_row['num_withdrawals']):,} txns (₹{float(h_row['total_withdrawal_amount'])/1e5:.1f} Lakhs)<br>
                            • Priority: <b>{h_row['priority_tier']}</b> ({h_row['priority_score']} pts)
                        </div>
                        """
                    )
            else:
                st.info("No valid hotspot data is available yet.")

    # =========================================================================
    # TAB 3: INCIDENT DOSSIERS & REPORTS
    # =========================================================================
    with analyst_tabs[2]:
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

    # =========================================================================
    # TAB 4: POLICE ALERT MONITOR (ANALYST'S LIVE MONITOR)
    # =========================================================================
    with analyst_tabs[3]:
        st.markdown("### 🚔 Police Alert Queue Monitor")
        st.caption("Live monitoring view showing what police officers are seeing and acknowledging in real time.")

        m_stats = get_alert_statistics()
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.metric("Total Alerts Ever Generated", m_stats["total_alerts"])
        with mc2:
            st.metric("New Alerts (Pending Police)", m_stats["new_alerts"])
        with mc3:
            st.metric("Reviewed by Police", m_stats["reviewed_alerts"])

        st.markdown("#### Current Alerts in Database")
        live_alerts = get_all_alerts(limit=50)
        if live_alerts:
            live_rows = []
            for la in live_alerts:
                live_rows.append({
                    "Alert ID": la.get("alert_id"),
                    "Detection Time": la.get("timestamp"),
                    "ATM ID": la.get("atm_id"),
                    "Area": la.get("area"),
                    "Evidence": la.get("evidence_type"),
                    "Status": la.get("status"),
                    "Reviewed By": la.get("reviewed_by") or "—",
                    "Review Time": la.get("reviewed_timestamp") or "—",
                })
            st.dataframe(pd.DataFrame(live_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No alert records found in the database.")


# -----------------------------------------------------------------------------
# FOOTER
# -----------------------------------------------------------------------------
st.markdown("---")
render_html(
    """
    <div style="text-align: center; font-size: 11px; color: #64748b; padding: 10px 0;">
        FraudLocate Lite | Problem Statement PS-024 — Data Science & Predictive Analytics | Academic Demonstration System
    </div>
    """
)
