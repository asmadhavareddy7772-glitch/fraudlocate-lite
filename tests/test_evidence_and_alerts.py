"""
FraudLocate Lite - Unit & Integration Tests for Evidence Processing & Alert System.
Validates:
- Standardized Evidence ID (EVD-YYYY-XXXXX) & Alert ID (ALERT-XXXXX) generation
- Technical/forensic metadata extraction (Image and Video)
- ATM & DBSCAN hotspot correlation
- Persistent SQLite alert storage CRUD operations
- Status management (New -> Acknowledged -> Under Review -> Resolved)
- 7-stage incident timeline generation
- One-click fraud event simulation (simulate_fraud_event)
- Law enforcement reports generation (Incident, Alert, Evidence)
- Email notification formatting and Demo Mode dispatch
"""

import os
import shutil
import tempfile
import pytest
import pandas as pd
from PIL import Image

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
    generate_alert_id,
    VALID_STATUSES,
)
from src.notification_service import (
    format_alert_email_html,
    send_fraud_alert_email,
    get_notification_logs,
    is_smtp_configured,
)
from src.evidence_processor import (
    generate_evidence_id,
    generate_case_id,
    extract_media_metadata,
    correlate_atm_with_hotspots,
    process_fraud_evidence,
    simulate_fraud_event,
)
from src.reports import (
    generate_incident_report_df,
    generate_alert_report_df,
    generate_evidence_report_df,
    generate_executive_briefing_text,
)
from utils.sample_evidence_generator import (
    ensure_sample_evidence_exists,
    SAMPLE_DIR,
)


@pytest.fixture(scope="module")
def sample_evidence():
    """Ensure sample synthetic evidence files exist."""
    ensure_sample_evidence_exists()
    return {
        "image_path": os.path.join(SAMPLE_DIR, "sample_cctv_1.jpg"),
        "video_path": os.path.join(SAMPLE_DIR, "sample_cctv_clip.mp4"),
    }


@pytest.fixture
def temp_db():
    """Provide an isolated temporary SQLite database for tests."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_alerts.db")
    init_alert_db(db_path)
    yield db_path
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestIdentifiersAndMetadata:
    """Test ID generators and media forensic extractors."""

    def test_generate_evidence_id(self):
        eid = generate_evidence_id()
        assert eid.startswith("EVD-")
        assert len(eid.split("-")) == 3

    def test_generate_case_id(self):
        cid = generate_case_id()
        assert cid.startswith("CASE-")

    def test_generate_alert_id(self):
        aid = generate_alert_id()
        assert aid.startswith("ALERT-")

    def test_extract_image_metadata(self, sample_evidence):
        img_path = sample_evidence["image_path"]
        meta = extract_media_metadata(img_path)
        assert meta["media_type"] == "Image"
        assert meta["file_size_kb"] > 0
        assert meta["width"] == 720
        assert meta["height"] == 480
        assert meta["extension"] == "jpg"

    def test_extract_video_metadata(self, sample_evidence):
        vid_path = sample_evidence["video_path"]
        meta = extract_media_metadata(vid_path)
        assert meta["media_type"] == "Video"
        assert meta["file_size_kb"] > 0
        assert meta["width"] == 640
        assert meta["height"] == 480
        assert meta["duration_seconds"] > 0


class TestAlertStoreCRUDAndStatus:
    """Test persistent SQLite alert storage operations and status lifecycle."""

    def test_insert_and_retrieve_alert(self, temp_db):
        alert_data = {
            "alert_id": "ALERT-10001",
            "evidence_id": "EVD-2026-00125",
            "complaint_id": "CASE-2026-09999",
            "timestamp": "2026-10-02 10:00:00",
            "atm_id": "ATM_HYD_102",
            "atm_name": "HDFC Maitrivanam",
            "latitude": 17.4389,
            "longitude": 78.4514,
            "area": "Ameerpet",
            "city": "Hyderabad",
            "amount": 35000.0,
            "evidence_type": "Image",
            "evidence_path": "data/sample_evidence/sample_cctv_1.jpg",
            "analysis_result": "Potential Fraud Event: Rapid cashout series.",
            "severity": "High Priority",
            "detection_status": "Alert Generated",
            "recommended_action": "Dispatch patrol unit.",
            "notification_status": "Sent (Demo Mode)",
            "status": "New",
            "cluster_id": 0,
            "hotspot_score": 85.0,
        }

        inserted_id = insert_alert(alert_data, db_path=temp_db)
        assert inserted_id == "ALERT-10001"

        fetched = get_alert_by_id("ALERT-10001", db_path=temp_db)
        assert fetched is not None
        assert fetched["atm_id"] == "ATM_HYD_102"
        assert fetched["status"] in ["NEW", "New"]
        assert fetched["amount"] == 35000.0

    def test_lifecycle_status_transitions(self, temp_db):
        alert_data = {
            "alert_id": "ALERT-10002",
            "evidence_id": "EVD-2026-00126",
            "complaint_id": "CASE-2026-00002",
            "atm_id": "ATM_1",
            "atm_name": "ATM 1",
            "latitude": 17.4,
            "longitude": 78.4,
            "area": "Zone",
            "city": "Hyderabad",
            "evidence_type": "Image",
            "analysis_result": "Analysis Completed",
            "severity": "High Priority",
            "detection_status": "Alert Generated",
            "recommended_action": "Inspect kiosk",
            "notification_status": "Sent",
            "status": "NEW",
        }
        insert_alert(alert_data, db_path=temp_db)

        # 1. Verify New
        active = get_active_alerts(db_path=temp_db)
        assert len(active) == 1
        assert active[0]["status"] == "NEW"

        # 2. Transition to REVIEWED
        mark_alert_reviewed("ALERT-10002", reviewer_name="TS-POLICE-101 (Insp. Vikram Reddy)", db_path=temp_db)
        a_ack = get_alert_by_id("ALERT-10002", db_path=temp_db)
        assert a_ack["status"] == "REVIEWED"
        assert "TS-POLICE-101" in a_ack["reviewed_by"]

        # 3. Transition to RESOLVED
        from src.alert_store import mark_alert_resolved
        mark_alert_resolved("ALERT-10002", reviewer_name="TS-POLICE-101", notes="Kiosk secured", db_path=temp_db)
        a_res = get_alert_by_id("ALERT-10002", db_path=temp_db)
        assert a_res["status"] == "RESOLVED"

    def test_alert_statistics_kpis(self, temp_db):
        stats_initial = get_alert_statistics(db_path=temp_db)
        assert stats_initial["total_alerts"] == 0

        insert_alert(
            {
                "alert_id": "ALERT-90001",
                "evidence_id": "EVD-2026-90001",
                "complaint_id": "CASE-2026-90001",
                "atm_id": "ATM_1",
                "atm_name": "ATM 1",
                "latitude": 17.4,
                "longitude": 78.4,
                "area": "Zone",
                "city": "Hyderabad",
                "amount": 50000.0,
                "evidence_type": "Image",
                "analysis_result": "Potential Fraud Event",
                "severity": "Critical Priority",
                "detection_status": "Alert Generated",
                "recommended_action": "Action",
                "notification_status": "Sent",
                "status": "New",
            },
            db_path=temp_db,
        )

        stats_after = get_alert_statistics(db_path=temp_db)
        assert stats_after["total_alerts"] == 1
        assert stats_after["new_alerts"] == 1
        assert stats_after["total_cases"] == 1
        assert stats_after["evidence_analyzed"] == 1
        assert stats_after["total_flagged_amount"] == 50000.0


class TestNotificationService:
    """Test email formatting and dispatch in Demo Mode."""

    def test_format_alert_email_html(self):
        alert_payload = {
            "alert_id": "ALERT-00125",
            "complaint_id": "CASE-2026-1024",
            "atm_id": "ATM_HYD_102",
            "atm_name": "HDFC Maitrivanam",
            "area": "Ameerpet Commercial Hub",
            "city": "Hyderabad",
            "amount": 25000.0,
            "evidence_type": "Image",
            "severity": "High Priority",
            "recommended_action": "Dispatch Tiger-1",
            "analysis_result": "Potential Fraud Event: Sequential cashout.",
            "cluster_id": 0,
        }
        html = format_alert_email_html(alert_payload)
        assert "ALERT-00125" in html
        assert "CASE-2026-1024" in html
        assert "ATM_HYD_102" in html
        assert "₹25,000" in html
        assert "High Priority" in html

    def test_send_fraud_alert_email_demo_mode(self):
        alert_payload = {
            "alert_id": "ALERT-00188",
            "complaint_id": "CASE-2026-1088",
            "atm_id": "ATM_HYD_201",
            "atm_name": "Kotak Cyber Towers",
            "area": "Madhapur",
            "city": "Hyderabad",
            "latitude": 17.448600,
            "longitude": 78.390800,
            "amount": 40000.0,
            "evidence_type": "Video",
            "severity": "Critical Priority",
            "recommended_action": "Check CCTV",
            "analysis_result": "Potential Fraud Event",
        }
        dispatch = send_fraud_alert_email(alert_payload, recipient_override="demo.police@test.org")
        assert dispatch is not None
        assert "DELIVERED" in dispatch["status"]
        assert dispatch["recipient"] == "demo.police@test.org"
        assert dispatch["alert_id"] == "ALERT-00188"
        assert dispatch["subject"] == "🚨 FRAUD ALERT – ATM ACTIVITY DETECTED"
        assert "https://www.google.com/maps?q=17.4486,78.3908" in dispatch["map_link"]

    def test_clean_email_text_and_location_link(self):
        from src.notification_service import (
            format_alert_email_text,
            generate_google_maps_link,
            generate_osm_link,
        )

        alert_payload = {
            "alert_id": "ALERT-001",
            "evidence_type": "CCTV Video",
            "timestamp": "10:42:15 AM",
            "atm_id": "ATM-024",
            "area": "Hyderabad",
            "latitude": 17.448612,
            "longitude": 78.390823,
            "evidence_id": "EVD-2026-00125",
        }

        text_body = format_alert_email_text(alert_payload)
        assert "FraudLocate Lite – Police Alert" in text_body
        assert "A potential fraud event has been detected from submitted evidence." in text_body
        assert "ALERT-001" in text_body
        assert "CCTV Video" in text_body
        assert "10:42:15 AM" in text_body
        assert "ATM-024" in text_body
        assert "17.448612" in text_body
        assert "78.390823" in text_body
        assert "VIEW ATM LOCATION:" in text_body
        assert "https://www.google.com/maps?q=17.448612,78.390823" in text_body
        assert "Academic Demonstration System" in text_body

        # Assert no technical code dumps in email text
        assert "def " not in text_body
        assert "{'latitude'" not in text_body
        assert "Traceback" not in text_body

        # Check map links
        gmap = generate_google_maps_link(17.4486, 78.3908)
        osm = generate_osm_link(17.4486, 78.3908)
        assert gmap == "https://www.google.com/maps?q=17.4486,78.3908"
        assert "openstreetmap.org" in osm


class TestHotspotCorrelationAndEndToEnd:
    """Test correlation with DBSCAN hotspots, timeline generation, and one-click simulation."""

    def test_hotspot_correlation(self):
        ranked_hotspots = pd.DataFrame([
            {
                "cluster_id": 0,
                "cluster_label": "Hotspot #0 (Ameerpet)",
                "primary_area": "Ameerpet",
                "centroid_lat": 17.4375,
                "centroid_lon": 78.4482,
                "approx_radius_km": 0.8,
                "priority_score": 88.0,
                "priority_tier": "High Priority",
            }
        ])

        corr = correlate_atm_with_hotspots(
            atm_id="ATM_HYD_101",
            atm_lat=17.4380,
            atm_lon=78.4490,
            ranked_hotspots_df=ranked_hotspots,
        )
        assert corr["is_in_hotspot"] is True
        assert corr["cluster_id"] == 0

    def test_complete_end_to_end_pipeline_with_timeline(self, sample_evidence, temp_db):
        img_path = sample_evidence["image_path"]

        atm_info = {
            "atm_id": "ATM_HYD_102",
            "atm_name": "HDFC 24x7 Cash Point - Maitrivanam",
            "latitude": 17.438924,
            "longitude": 78.451465,
            "area": "Ameerpet Commercial Hub",
            "city": "Hyderabad",
        }

        ranked_hotspots = pd.DataFrame([
            {
                "cluster_id": 0,
                "cluster_label": "Hotspot #0 (Ameerpet)",
                "primary_area": "Ameerpet Commercial Hub",
                "centroid_lat": 17.4375,
                "centroid_lon": 78.4482,
                "approx_radius_km": 0.6,
                "priority_score": 89.2,
                "priority_tier": "High Priority",
            }
        ])

        historical_df = pd.DataFrame([
            {"atm_id": "ATM_HYD_102", "withdrawal_amount": 25000},
            {"atm_id": "ATM_HYD_102", "withdrawal_amount": 30000},
        ])

        result = process_fraud_evidence(
            file_path=img_path,
            atm_info=atm_info,
            complaint_id="CASE-2026-00125",
            flagged_amount=25000.0,
            ranked_hotspots_df=ranked_hotspots,
            historical_df=historical_df,
        )

        assert result["status"] == "SUCCESS"
        assert result["alert_id"].startswith("ALERT-")
        assert result["evidence_id"].startswith("EVD-")
        assert result["complaint_id"] == "CASE-2026-00125"

        # Verify 7-step timeline
        timeline = result["timeline"]
        assert "evidence_uploaded" in timeline
        assert "evidence_processed" in timeline
        assert "fraud_event_created" in timeline
        assert "alert_generated" in timeline
        assert "police_notified" in timeline

    def test_one_click_simulate_fraud_event(self, sample_evidence):
        historical_df = pd.DataFrame([
            {"atm_id": "ATM_HYD_102", "withdrawal_amount": 25000},
            {"atm_id": "ATM_HYD_201", "withdrawal_amount": 40000},
        ])

        sim_res = simulate_fraud_event(historical_df=historical_df, sample_type="Image")
        assert sim_res["status"] == "SUCCESS"
        assert sim_res["alert_id"].startswith("ALERT-")
        assert sim_res["evidence_id"].startswith("EVD-")
        assert "patrol_recommendation" in sim_res
        assert sim_res["patrol_recommendation"]["estimated_travel_time"] is not None


class TestReportsGeneration:
    """Test incident, alert, and evidence report generators."""

    def test_generate_incident_report(self):
        df = generate_incident_report_df()
        assert isinstance(df, pd.DataFrame)

    def test_generate_alert_report(self):
        df = generate_alert_report_df()
        assert isinstance(df, pd.DataFrame)

    def test_generate_evidence_report(self):
        df = generate_evidence_report_df()
        assert isinstance(df, pd.DataFrame)

    def test_generate_executive_briefing(self):
        briefing = generate_executive_briefing_text()
        assert "FRAUDLOCATE LITE" in briefing
        assert "PS-024" in briefing


class TestPoliceAuthAndPersistentLifecycle:
    """
    Test suite specifically testing the user-requested requirements from Section 29:
    - Role-based authentication (Analyst & Police)
    - Test 1: Create one fraud alert -> All=1, New=1, Reviewed=0
    - Test 2: Review the alert -> All=1, New=0, Reviewed=1
    - Test 3: Create another alert -> All=2, New=1, Reviewed=1
    - Test 4: Refresh simulation (re-read stats from DB) -> All=2, New=1, Reviewed=1
    - Test 5: Restart application (re-open DB connection) -> All=2, New=1, Reviewed=1
    - Test 6: Login again -> Same persistent history!
    """

    def test_authentication_system(self, temp_db):
        from src.auth import (
            init_user_db,
            seed_demo_users_if_empty,
            authenticate_user,
            hash_password,
            verify_password,
        )

        init_user_db(temp_db)
        seed_demo_users_if_empty(temp_db)

        # 1. Test password hashing & salt
        salt, p_hash = hash_password("secretpass123")
        assert verify_password("secretpass123", salt, p_hash) is True
        assert verify_password("wrongpass", salt, p_hash) is False

        # 2. Test Analyst Login
        analyst = authenticate_user("analyst", "analyst123", db_path=temp_db)
        assert analyst is not None
        assert analyst["role"] == "ANALYST"
        assert "password_hash" not in analyst

        # 3. Test Police Login by Username
        officer = authenticate_user("officer.vikram", "police101", db_path=temp_db)
        assert officer is not None
        assert officer["role"] == "POLICE"
        assert officer["police_id"] == "TS-POLICE-101"

        # 4. Test Police Login by Police ID
        officer_by_id = authenticate_user("TS-POLICE-101", "police101", db_path=temp_db)
        assert officer_by_id is not None
        assert officer_by_id["username"] == "officer.vikram"

        # 5. Invalid credentials rejection
        assert authenticate_user("analyst", "wrongpass", db_path=temp_db) is None
        assert authenticate_user("unknown_user", "somepass", db_path=temp_db) is None

    def test_prompt_section_29_exact_flow(self, temp_db):
        """
        Executes Test 1 through Test 6 from User Request Section 29:
        Test 1: Create 1 alert -> All=1, New=1, Reviewed=0
        Test 2: Review the alert -> All=1, New=0, Reviewed=1
        Test 3: Create 2nd alert -> All=2, New=1, Reviewed=1
        Test 4: Refresh page -> All=2, New=1, Reviewed=1
        Test 5: Restart application -> All=2, New=1, Reviewed=1
        Test 6: Login again -> Same persistent history
        """
        from src.alert_store import (
            insert_alert,
            get_all_alerts,
            get_new_alerts,
            get_reviewed_alerts,
            mark_alert_reviewed,
            get_alert_statistics,
        )
        from src.auth import authenticate_user, seed_demo_users_if_empty

        seed_demo_users_if_empty(temp_db)

        # -------------------------------------------------------------
        # Test 1: Create one fraud alert.
        # Expected: All = 1, New = 1, Reviewed = 0
        # -------------------------------------------------------------
        alert_1 = {
            "alert_id": "ALERT-TEST-001",
            "evidence_id": "EVD-TEST-001",
            "complaint_id": "CASE-TEST-001",
            "timestamp": "2026-10-02 10:00:00",
            "atm_id": "ATM-HYD-024",
            "atm_name": "SBI Cyber Kiosk",
            "latitude": 17.4486,
            "longitude": 78.3908,
            "area": "Madhapur",
            "city": "Hyderabad",
            "amount": 25000.0,
            "evidence_type": "CCTV Video",
            "analysis_result": "Potential Fraud Event Detected",
            "severity": "High Priority",
            "status": "NEW",
        }
        insert_alert(alert_1, db_path=temp_db)

        stats_1 = get_alert_statistics(db_path=temp_db)
        assert stats_1["total_alerts"] == 1, "Test 1 Failed: All should be 1"
        assert stats_1["new_alerts"] == 1, "Test 1 Failed: New should be 1"
        assert stats_1["reviewed_alerts"] == 0, "Test 1 Failed: Reviewed should be 0"

        # Verify segregated query lists
        new_list_1 = get_new_alerts(db_path=temp_db)
        rev_list_1 = get_reviewed_alerts(db_path=temp_db)
        all_list_1 = get_all_alerts(db_path=temp_db)
        assert len(new_list_1) == 1
        assert len(rev_list_1) == 0
        assert len(all_list_1) == 1

        # -------------------------------------------------------------
        # Test 2: Review the alert.
        # Expected: All = 1, New = 0, Reviewed = 1
        # -------------------------------------------------------------
        police_user = authenticate_user("TS-POLICE-101", "police101", db_path=temp_db)
        assert police_user is not None

        mark_alert_reviewed(
            "ALERT-TEST-001",
            reviewer_name=f"{police_user['police_id']} ({police_user['full_name']})",
            db_path=temp_db,
        )

        stats_2 = get_alert_statistics(db_path=temp_db)
        assert stats_2["total_alerts"] == 1, "Test 2 Failed: All should be 1"
        assert stats_2["new_alerts"] == 0, "Test 2 Failed: New should be 0"
        assert stats_2["reviewed_alerts"] == 1, "Test 2 Failed: Reviewed should be 1"

        new_list_2 = get_new_alerts(db_path=temp_db)
        rev_list_2 = get_reviewed_alerts(db_path=temp_db)
        all_list_2 = get_all_alerts(db_path=temp_db)
        assert len(new_list_2) == 0, "Reviewed alert must not appear in New Alerts"
        assert len(rev_list_2) == 1, "Reviewed alert must appear in Reviewed Alerts"
        assert len(all_list_2) == 1, "Reviewed alert must remain in All Alerts"
        assert "TS-POLICE-101" in rev_list_2[0]["reviewed_by"]

        # -------------------------------------------------------------
        # Test 3: Create another alert.
        # Expected: All = 2, New = 1, Reviewed = 1
        # -------------------------------------------------------------
        alert_2 = {
            "alert_id": "ALERT-TEST-002",
            "evidence_id": "EVD-TEST-002",
            "complaint_id": "CASE-TEST-002",
            "timestamp": "2026-10-02 10:15:00",
            "atm_id": "ATM-HYD-102",
            "atm_name": "HDFC Cash Point",
            "latitude": 17.4389,
            "longitude": 78.4514,
            "area": "Ameerpet",
            "city": "Hyderabad",
            "amount": 30000.0,
            "evidence_type": "Image",
            "analysis_result": "Potential Fraud Event Detected",
            "severity": "Critical Priority",
            "status": "NEW",
        }
        insert_alert(alert_2, db_path=temp_db)

        stats_3 = get_alert_statistics(db_path=temp_db)
        assert stats_3["total_alerts"] == 2, "Test 3 Failed: All should be 2"
        assert stats_3["new_alerts"] == 1, "Test 3 Failed: New should be 1"
        assert stats_3["reviewed_alerts"] == 1, "Test 3 Failed: Reviewed should be 1"

        new_list_3 = get_new_alerts(db_path=temp_db)
        rev_list_3 = get_reviewed_alerts(db_path=temp_db)
        all_list_3 = get_all_alerts(db_path=temp_db)
        assert len(new_list_3) == 1
        assert len(rev_list_3) == 1
        assert len(all_list_3) == 2
        assert new_list_3[0]["alert_id"] == "ALERT-TEST-002"
        assert rev_list_3[0]["alert_id"] == "ALERT-TEST-001"

        # -------------------------------------------------------------
        # Test 4: Refresh page simulation (re-query database).
        # Expected: All = 2, New = 1, Reviewed = 1
        # -------------------------------------------------------------
        stats_4 = get_alert_statistics(db_path=temp_db)
        assert stats_4["total_alerts"] == 2, "Test 4 Failed: All should be 2 after refresh"
        assert stats_4["new_alerts"] == 1, "Test 4 Failed: New should be 1 after refresh"
        assert stats_4["reviewed_alerts"] == 1, "Test 4 Failed: Reviewed should be 1 after refresh"

        # -------------------------------------------------------------
        # Test 5: Restart application simulation (new connection to DB).
        # Expected: All = 2, New = 1, Reviewed = 1
        # -------------------------------------------------------------
        import sqlite3
        # Connect fresh to simulate cold application restart
        fresh_conn = sqlite3.connect(temp_db)
        fresh_cursor = fresh_conn.cursor()
        fresh_cursor.execute("SELECT COUNT(*) FROM alerts")
        fresh_total = fresh_cursor.fetchone()[0]
        fresh_cursor.execute("SELECT COUNT(*) FROM alerts WHERE UPPER(status) = 'NEW'")
        fresh_new = fresh_cursor.fetchone()[0]
        fresh_cursor.execute("SELECT COUNT(*) FROM alerts WHERE UPPER(status) = 'REVIEWED'")
        fresh_reviewed = fresh_cursor.fetchone()[0]
        fresh_conn.close()

        assert fresh_total == 2, "Test 5 Failed: Persistent total should be 2 across restart"
        assert fresh_new == 1, "Test 5 Failed: Persistent new should be 1 across restart"
        assert fresh_reviewed == 1, "Test 5 Failed: Persistent reviewed should be 1 across restart"

        # -------------------------------------------------------------
        # Test 6: Login again simulation.
        # Expected: Same persistent history.
        # -------------------------------------------------------------
        officer_login_again = authenticate_user("officer.vikram", "police101", db_path=temp_db)
        assert officer_login_again is not None

        history = get_all_alerts(limit=50, db_path=temp_db)
        assert len(history) == 2, "Test 6 Failed: Alert history should retain 2 alerts"
        # Chronological sort (newest first)
        assert history[0]["alert_id"] == "ALERT-TEST-002"
        assert history[1]["alert_id"] == "ALERT-TEST-001"

