"""
FraudLocate Lite - Reporting & Executive Intelligence Module.
Generates structured Incident Reports, Alert Dispatch Reports, and Evidence Inventory Reports
with downloadable CSV exports and executive briefing summaries.
"""

from typing import Dict, Any, List, Optional
import json
import pandas as pd
from datetime import datetime
from src.alert_store import get_all_alerts, get_alert_statistics
from src.notification_service import get_notification_logs


def generate_incident_report_df() -> pd.DataFrame:
    """Generate comprehensive incident report dataframe across all logged cases."""
    alerts = get_all_alerts(limit=200)
    if not alerts:
        return pd.DataFrame()

    rows = []
    for a in alerts:
        rows.append({
            "Alert ID": a.get("alert_id"),
            "Case Reference": a.get("complaint_id"),
            "Detection Timestamp": a.get("timestamp"),
            "ATM Identifier": a.get("atm_id"),
            "ATM Name": a.get("atm_name"),
            "Metropolitan Area": a.get("area"),
            "Loss Amount (₹)": a.get("amount", 0.0),
            "Media Format": a.get("evidence_type"),
            "Hotspot Cluster": f"Cluster #{a.get('cluster_id')}" if a.get("cluster_id") != -1 else "Unclustered",
            "Priority Score": a.get("hotspot_score", 0.0),
            "Operational Severity": a.get("severity"),
            "Incident Status": a.get("status", "New"),
            "Reviewing Officer": a.get("reviewed_by") or "Pending Review",
        })
    return pd.DataFrame(rows)


def generate_alert_report_df() -> pd.DataFrame:
    """Generate alert dispatch audit log and lifecycle status report."""
    alerts = get_all_alerts(limit=200)
    if not alerts:
        return pd.DataFrame()

    rows = []
    for a in alerts:
        rows.append({
            "Alert ID": a.get("alert_id"),
            "Generated At": a.get("timestamp"),
            "Notification Dispatch": a.get("notification_status"),
            "Current Status": a.get("status", "New"),
            "Review Flag": a.get("reviewed_status"),
            "Reviewed Timestamp": a.get("reviewed_timestamp") or "—",
            "Officer Identity": a.get("reviewed_by") or "—",
            "Officer Directives / Notes": a.get("officer_notes") or "—",
            "Recommended Action": a.get("recommended_action"),
        })
    return pd.DataFrame(rows)


def generate_evidence_report_df() -> pd.DataFrame:
    """Generate digital evidence asset inventory with forensic metadata."""
    alerts = get_all_alerts(limit=200)
    if not alerts:
        return pd.DataFrame()

    rows = []
    for a in alerts:
        meta = {}
        extra = a.get("extra_metadata")
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except Exception:
                extra = {}
        if isinstance(extra, dict):
            meta = extra.get("media", {})

        rows.append({
            "Evidence ID": a.get("evidence_id"),
            "Linked Alert": a.get("alert_id"),
            "Linked Case": a.get("complaint_id"),
            "Media Type": a.get("evidence_type"),
            "File Name": meta.get("file_name", "N/A"),
            "File Size (KB)": meta.get("file_size_kb", 0),
            "Dimensions": f"{meta.get('width', 'N/A')}x{meta.get('height', 'N/A')}",
            "Video Duration (s)": meta.get("duration_seconds", "N/A"),
            "Associated Kiosk": a.get("atm_id"),
            "Inspection Time": a.get("timestamp"),
        })
    return pd.DataFrame(rows)


def generate_executive_briefing_text() -> str:
    """Render executive text briefing for supervisory review."""
    stats = get_alert_statistics()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""
================================================================================
           FRAUDLOCATE LITE — LAW ENFORCEMENT EXECUTIVE BRIEFING
================================================================================
Generated: {now_str}
Problem Statement: PS-024 (Data Science & Predictive Analytics)
Operational Status: Active Decision-Support Simulation

1. INCIDENT & PATROL METRICS OVERVIEW
--------------------------------------------------------------------------------
• Total Recorded Fraud Cases:        {stats.get('total_cases', 0)}
• Total Evidence Items Analyzed:     {stats.get('evidence_analyzed', 0)}
• Total Incident Alerts Generated:   {stats.get('total_alerts', 0)}
• Active / New Alerts:               {stats.get('new_alerts', 0)}
• Acknowledged Incidents:            {stats.get('acknowledged_alerts', 0)}
• Under Active Review:               {stats.get('under_review_alerts', 0)}
• Resolved Cases:                    {stats.get('resolved_alerts', 0)}
• Cumulative Flagged Amount:         ₹{stats.get('total_flagged_amount', 0):,.2f}

2. ALGORITHMIC INTELLIGENCE SUMMARY
--------------------------------------------------------------------------------
• Geospatial Engine: DBSCAN on coordinate radians with spherical Haversine metric.
• Resource Index: 4-factor Patrol Coverage Priority Scoring (0-100 pts).
• Routing Heuristic: Greedy Nearest-Neighbor Heuristic from Central Police HQ.
• Dual Notifications: Local SQLite event bus + MIME HTML email dispatch.

3. ETHICAL & SCOPE NOTICE
--------------------------------------------------------------------------------
FraudLocate Lite operates strictly on synthetic / simulated data for decision support.
Does not perform real-world surveillance, criminal tracking, or guaranteed prediction.
================================================================================
"""
