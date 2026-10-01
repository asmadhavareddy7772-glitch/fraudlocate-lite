"""
FraudLocate Lite - Persistent Alert & Fraud Event Database.
Uses SQLite for reliable, zero-configuration local persistence across browser sessions and multi-device demos.
Supports full lifecycle status management: New -> Acknowledged -> Under Review -> Resolved.
"""

import os
import sqlite3
import json
import random
from datetime import datetime
from typing import Dict, Any, List, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "alerts.db")

VALID_STATUSES = ["New", "Acknowledged", "Under Review", "Resolved"]


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create or return a thread-safe connection with dict-like row access."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def generate_alert_id() -> str:
    """Generate standardized Alert ID in ALERT-XXXXX format."""
    rand_num = random.randint(10000, 99999)
    return f"ALERT-{rand_num}"


def init_alert_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the alerts table and indices with status and timeline support."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL,
                complaint_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                atm_id TEXT NOT NULL,
                atm_name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                area TEXT NOT NULL,
                city TEXT NOT NULL,
                amount REAL,
                evidence_type TEXT NOT NULL,
                evidence_path TEXT,
                analysis_result TEXT NOT NULL,
                severity TEXT NOT NULL,
                detection_status TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                notification_status TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'New',
                reviewed_status TEXT NOT NULL DEFAULT 'Unreviewed',
                reviewed_timestamp TEXT,
                reviewed_by TEXT,
                officer_notes TEXT,
                cluster_id INTEGER DEFAULT -1,
                hotspot_score REAL DEFAULT 0.0,
                timeline TEXT,
                extra_metadata TEXT
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_atm ON alerts(atm_id)")

        # Migration: ensure status, officer_notes, timeline columns exist
        cursor.execute("PRAGMA table_info(alerts)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "status" not in columns:
            cursor.execute("ALTER TABLE alerts ADD COLUMN status TEXT NOT NULL DEFAULT 'New'")
        if "officer_notes" not in columns:
            cursor.execute("ALTER TABLE alerts ADD COLUMN officer_notes TEXT")
        if "timeline" not in columns:
            cursor.execute("ALTER TABLE alerts ADD COLUMN timeline TEXT")

        conn.commit()


def insert_alert(alert_data: Dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> str:
    """
    Insert or update a fraud alert record into SQLite.
    Returns the alert_id.
    """
    init_alert_db(db_path)
    alert_id = alert_data.get("alert_id")
    if not alert_id:
        alert_id = generate_alert_id()

    status = alert_data.get("status", "New")
    if status not in VALID_STATUSES:
        status = "New"

    reviewed_status = alert_data.get("reviewed_status")
    if not reviewed_status:
        reviewed_status = "Reviewed" if status in ["Acknowledged", "Under Review", "Resolved"] else "Unreviewed"

    extra_meta = alert_data.get("extra_metadata")
    if isinstance(extra_meta, (dict, list)):
        extra_meta = json.dumps(extra_meta)
    elif extra_meta is None:
        extra_meta = "{}"

    timeline_data = alert_data.get("timeline")
    if isinstance(timeline_data, (dict, list)):
        timeline_data = json.dumps(timeline_data)
    elif timeline_data is None:
        timeline_data = json.dumps({
            "evidence_uploaded": alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "evidence_processed": alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "fraud_event_created": alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "alert_generated": alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "police_notified": alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "alert_reviewed": None,
            "case_status_updated": None,
        })

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO alerts (
                alert_id, evidence_id, complaint_id, timestamp, atm_id, atm_name,
                latitude, longitude, area, city, amount, evidence_type, evidence_path,
                analysis_result, severity, detection_status, recommended_action,
                notification_status, status, reviewed_status, reviewed_timestamp, reviewed_by,
                officer_notes, cluster_id, hotspot_score, timeline, extra_metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert_id,
                alert_data.get("evidence_id", "EVD-2026-00001"),
                alert_data.get("complaint_id", "CASE-2026-00001"),
                alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                alert_data.get("atm_id", "ATM_GENERIC"),
                alert_data.get("atm_name", "Metropolitan ATM Kiosk"),
                float(alert_data.get("latitude", 17.3850)),
                float(alert_data.get("longitude", 78.4867)),
                alert_data.get("area", "Hyderabad Central"),
                alert_data.get("city", "Hyderabad"),
                float(alert_data.get("amount", 25000.0)) if alert_data.get("amount") is not None else None,
                alert_data.get("evidence_type", "Image"),
                alert_data.get("evidence_path", ""),
                alert_data.get("analysis_result", "Potential Fraud Event Detected"),
                alert_data.get("severity", "High Priority"),
                alert_data.get("detection_status", "Alert Generated"),
                alert_data.get("recommended_action", "Dispatch nearest patrol unit to verify ATM perimeter."),
                alert_data.get("notification_status", "Sent (In-App + Email)"),
                status,
                reviewed_status,
                alert_data.get("reviewed_timestamp"),
                alert_data.get("reviewed_by"),
                alert_data.get("officer_notes"),
                int(alert_data.get("cluster_id", -1)),
                float(alert_data.get("hotspot_score", 0.0)),
                timeline_data,
                extra_meta,
            ),
        )
        conn.commit()

    return alert_id


def get_all_alerts(limit: int = 100, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve all alerts ordered by detection timestamp descending."""
    init_alert_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_active_alerts(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve new or unreviewed alerts."""
    init_alert_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM alerts 
            WHERE status = 'New' OR reviewed_status = 'Unreviewed' 
            ORDER BY timestamp DESC
            """
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_alerts_by_status(status: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve alerts matching a specific status."""
    init_alert_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts WHERE status = ? ORDER BY timestamp DESC", (status,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_alert_by_id(alert_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetch single alert by its unique alert_id."""
    init_alert_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_alert_status(
    alert_id: str,
    new_status: str,
    officer_name: str = "Officer On Duty",
    notes: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> bool:
    """Update status, reviewer, officer notes, and incident timeline."""
    init_alert_db(db_path)
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {VALID_STATUSES}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reviewed_status = "Reviewed" if new_status in ["Acknowledged", "Under Review", "Resolved"] else "Unreviewed"

    # Fetch existing timeline to update
    alert = get_alert_by_id(alert_id, db_path=db_path)
    timeline = {}
    if alert and alert.get("timeline"):
        try:
            timeline = json.loads(alert["timeline"])
        except Exception:
            timeline = {}

    timeline["alert_reviewed"] = now_str
    timeline["case_status_updated"] = f"{now_str} (Status: {new_status})"

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE alerts
            SET status = ?,
                reviewed_status = ?,
                reviewed_timestamp = ?,
                reviewed_by = ?,
                officer_notes = COALESCE(?, officer_notes),
                timeline = ?
            WHERE alert_id = ?
            """,
            (new_status, reviewed_status, now_str, officer_name, notes, json.dumps(timeline), alert_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def mark_alert_reviewed(
    alert_id: str,
    reviewer_name: str = "Officer On Duty",
    db_path: str = DEFAULT_DB_PATH,
) -> bool:
    """Mark an alert as Acknowledged / Reviewed."""
    return update_alert_status(
        alert_id=alert_id,
        new_status="Acknowledged",
        officer_name=reviewer_name,
        notes="Reviewed and acknowledged by patrol dispatcher.",
        db_path=db_path,
    )


def get_alert_statistics(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Return summary counts of total, new, under review, and resolved alerts."""
    init_alert_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM alerts")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'New' OR reviewed_status = 'Unreviewed'")
        new_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'Acknowledged'")
        ack_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'Under Review'")
        under_review_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'Resolved'")
        resolved_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT complaint_id) FROM alerts")
        total_cases = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT evidence_id) FROM alerts")
        evidence_count = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(amount) FROM alerts")
        amt_sum = cursor.fetchone()[0] or 0.0

        return {
            "total_alerts": total,
            "new_alerts": new_count,
            "active_unreviewed": new_count,
            "acknowledged_alerts": ack_count,
            "under_review_alerts": under_review_count,
            "resolved_alerts": resolved_count,
            "reviewed": total - new_count,
            "total_cases": total_cases,
            "evidence_analyzed": evidence_count,
            "total_flagged_amount": amt_sum,
        }


def seed_demo_alerts_if_empty(db_path: str = DEFAULT_DB_PATH) -> None:
    """Seed baseline demo alerts with full incident timelines."""
    init_alert_db(db_path)
    stats = get_alert_statistics(db_path)
    if stats["total_alerts"] == 0:
        demo_alerts = [
            {
                "alert_id": "ALERT-00124",
                "evidence_id": "EVD-2026-00124",
                "complaint_id": "CASE-2026-1024",
                "timestamp": "2026-09-30 14:22:15",
                "atm_id": "ATM_HYD_102",
                "atm_name": "HDFC 24x7 Cash Point - Maitrivanam",
                "latitude": 17.438924,
                "longitude": 78.451465,
                "area": "Ameerpet Commercial Hub",
                "city": "Hyderabad",
                "amount": 25000.0,
                "evidence_type": "Image",
                "evidence_path": "data/sample_evidence/sample_cctv_1.jpg",
                "analysis_result": "Potential Fraud Event: High-velocity ATM cash withdrawal sequence.",
                "severity": "High Priority",
                "detection_status": "Alert Generated",
                "recommended_action": "Direct Tiger-Patrol-1 to verify Maitrivanam kiosk cluster.",
                "notification_status": "Sent (In-App + Email)",
                "status": "Acknowledged",
                "reviewed_status": "Reviewed",
                "reviewed_timestamp": "2026-09-30 14:35:10",
                "reviewed_by": "Inspector R. Sharma (Cyber Crime Cell)",
                "officer_notes": "Kiosk verified. Nearby branch nodal officer alerted.",
                "cluster_id": 0,
                "hotspot_score": 88.5,
                "timeline": {
                    "evidence_uploaded": "2026-09-30 14:22:10",
                    "evidence_processed": "2026-09-30 14:22:12",
                    "fraud_event_created": "2026-09-30 14:22:13",
                    "alert_generated": "2026-09-30 14:22:14",
                    "police_notified": "2026-09-30 14:22:15",
                    "alert_reviewed": "2026-09-30 14:35:10",
                    "case_status_updated": "2026-09-30 14:35:10 (Status: Acknowledged)",
                },
            },
            {
                "alert_id": "ALERT-00125",
                "evidence_id": "EVD-2026-00125",
                "complaint_id": "CASE-2026-1088",
                "timestamp": "2026-10-01 18:47:30",
                "atm_id": "ATM_HYD_201",
                "atm_name": "Kotak ATM - Cyber Towers Concourse",
                "latitude": 17.4486,
                "longitude": 78.3908,
                "area": "Madhapur Tech Corridor",
                "city": "Hyderabad",
                "amount": 40000.0,
                "evidence_type": "Video",
                "evidence_path": "data/sample_evidence/sample_cctv_clip.mp4",
                "analysis_result": "Potential Fraud Event: Rapid sequential mule card swipe transactions.",
                "severity": "Critical Priority",
                "detection_status": "Alert Generated",
                "recommended_action": "Alert Madhapur Sector mobile patrol unit; request kiosk CCTV preservation.",
                "notification_status": "Sent (In-App + Email)",
                "status": "New",
                "reviewed_status": "Unreviewed",
                "cluster_id": 1,
                "hotspot_score": 92.4,
                "timeline": {
                    "evidence_uploaded": "2026-10-01 18:47:25",
                    "evidence_processed": "2026-10-01 18:47:27",
                    "fraud_event_created": "2026-10-01 18:47:28",
                    "alert_generated": "2026-10-01 18:47:29",
                    "police_notified": "2026-10-01 18:47:30",
                    "alert_reviewed": None,
                    "case_status_updated": None,
                },
            },
        ]
        for a in demo_alerts:
            insert_alert(a, db_path=db_path)
