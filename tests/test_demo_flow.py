"""
FraudLocate Lite - End-to-End Demonstration Flow Test.
Simulates Laptop 1 (Analyst) and Laptop 2 (Police) workflow matching prompt specifications.
"""

import os
import shutil
import tempfile
import pytest

from src.alert_store import (
    init_alert_db,
    insert_alert,
    get_all_alerts,
    get_new_alerts,
    get_reviewed_alerts,
    get_resolved_alerts,
    mark_alert_reviewed,
    mark_alert_resolved,
    get_alert_statistics,
)
from src.auth import init_user_db, seed_demo_users_if_empty, authenticate_user
from src.evidence_processor import (
    process_fraud_evidence,
    generate_evidence_id,
    generate_case_id,
)
from utils.sample_evidence_generator import ensure_sample_evidence_exists, SAMPLE_DIR


@pytest.fixture
def demo_env():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "demo_alerts.db")
    init_alert_db(db_path)
    init_user_db(db_path)
    seed_demo_users_if_empty(db_path)
    ensure_sample_evidence_exists()
    yield db_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_laptop1_analyst_and_laptop2_police_demonstration(demo_env):
    db_path = demo_env

    # -------------------------------------------------------------------------
    # LAPTOP 1: ANALYST WORKFLOW
    # -------------------------------------------------------------------------
    # 1. Analyst logs in
    analyst_user = authenticate_user("analyst", "analyst123", db_path=db_path)
    assert analyst_user is not None
    assert analyst_user["role"] == "ANALYST"

    # 2. Analyst uploads evidence and runs fraud analysis
    sample_img = os.path.join(SAMPLE_DIR, "sample_cctv_1.jpg")
    atm_info = {
        "atm_id": "ATM-024",
        "atm_name": "HDFC Cyber Kiosk",
        "area": "Hyderabad",
        "city": "Hyderabad",
        "latitude": 17.4486,
        "longitude": 78.3908,
    }

    res = process_fraud_evidence(
        file_path=sample_img,
        atm_info=atm_info,
        complaint_id="CASE-DEMO-001",
        evidence_id="EVD-DEMO-001",
        flagged_amount=25000.0,
    )
    alert_id = res["alert_id"]
    assert alert_id.startswith("ALERT-")

    # 3. Alert is immediately stored in database with status NEW
    # Note: process_fraud_evidence uses default DEFAULT_DB_PATH, so let's also test direct insert_alert in demo_env
    alert_record = res["alert_data"]
    insert_alert(alert_record, db_path=db_path)

    # -------------------------------------------------------------------------
    # LAPTOP 2: POLICE WORKFLOW
    # -------------------------------------------------------------------------
    # 1. Police logs in using Police ID
    police_user = authenticate_user("TS-POLICE-101", "police101", db_path=db_path)
    assert police_user is not None
    assert police_user["role"] == "POLICE"

    # 2. Police Dashboard displays counters: All=1, New=1, Reviewed=0
    stats = get_alert_statistics(db_path=db_path)
    assert stats["total_alerts"] == 1
    assert stats["new_alerts"] == 1
    assert stats["reviewed_alerts"] == 0

    # 3. New alert appears in New Alerts queue
    new_alerts = get_new_alerts(db_path=db_path)
    assert len(new_alerts) == 1
    assert new_alerts[0]["alert_id"] == alert_id
    assert new_alerts[0]["status"] == "NEW"

    # 4. Police reviews the alert: status changes NEW -> REVIEWED
    reviewer_tag = f"{police_user['police_id']} ({police_user['full_name']})"
    rev_ok = mark_alert_reviewed(alert_id, reviewer_name=reviewer_tag, db_path=db_path)
    assert rev_ok is True

    # 5. Database updates immediately: All=1, New=0, Reviewed=1
    stats_after = get_alert_statistics(db_path=db_path)
    assert stats_after["total_alerts"] == 1
    assert stats_after["new_alerts"] == 0
    assert stats_after["reviewed_alerts"] == 1

    # 6. Alert automatically disappears from New Alerts list
    assert len(get_new_alerts(db_path=db_path)) == 0

    # 7. Alert appears in Reviewed Alerts
    rev_list = get_reviewed_alerts(db_path=db_path)
    assert len(rev_list) == 1
    assert rev_list[0]["alert_id"] == alert_id
    assert "TS-POLICE-101" in rev_list[0]["reviewed_by"]

    # 8. Alert remains permanently in All Alerts and Alert History
    all_list = get_all_alerts(db_path=db_path)
    assert len(all_list) == 1
    assert all_list[0]["alert_id"] == alert_id

    # 9. Optionally mark as RESOLVED
    res_ok = mark_alert_resolved(alert_id, reviewer_name=reviewer_tag, db_path=db_path)
    assert res_ok is True

    # When RESOLVED, it is neither in New nor Reviewed
    assert len(get_new_alerts(db_path=db_path)) == 0
    assert len(get_reviewed_alerts(db_path=db_path)) == 0
    assert len(get_resolved_alerts(db_path=db_path)) == 1
    assert len(get_all_alerts(db_path=db_path)) == 1
