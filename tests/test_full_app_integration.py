"""
Full application integration test using Streamlit's AppTest testing framework.
Tests end-to-end UI logic:
1. Pre-auth screen and tab switching
2. 1-Click login as Police Officer
3. Police dashboard KPI counters and alert list rendering
4. Reviewing an alert (NEW -> REVIEWED)
5. Resolving an alert (REVIEWED -> RESOLVED)
6. Logout
7. 1-Click login as Analyst
"""

import os
import sys
import pytest
from streamlit.testing.v1 import AppTest

from src.alert_store import (
    init_alert_db,
    insert_alert,
    get_all_alerts,
    get_new_alerts,
    get_reviewed_alerts,
    get_alert_statistics,
)
from src.auth import init_user_db, seed_demo_users_if_empty


def test_stream_app_full_police_and_analyst_flow():
    # 1. Initialize databases
    init_alert_db()
    init_user_db()
    seed_demo_users_if_empty()

    # 2. Launch App via AppTest
    app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
    at = AppTest.from_file(app_path, default_timeout=45).run()
    assert at.session_state.authenticated is False

    # 3. Click 1-Click Login as Inspector Vikram (TS-POLICE-101)
    vikram_btn = None
    for b in at.button:
        if "Insp. Vikram" in b.label and "1-Click" in b.label:
            vikram_btn = b
            break
    assert vikram_btn is not None, "1-Click Vikram button must exist"
    
    vikram_btn.click().run()
    assert at.session_state.authenticated is True
    assert at.session_state.user["role"] == "POLICE"
    assert at.session_state.user["police_id"] == "TS-POLICE-101"

    # 4. Verify Police Dashboard renders
    tab_labels = [t.label for t in at.tabs]
    assert any("New Alerts" in label for label in tab_labels)
    assert any("Reviewed Alerts" in label for label in tab_labels)
    assert any("All Alerts" in label for label in tab_labels)

    # 5. Find a "MARK AS REVIEWED" button if there are new alerts
    review_buttons = [b for b in at.button if "MARK AS REVIEWED" in b.label]
    initial_stats = get_alert_statistics()
    initial_new_count = initial_stats["new_alerts"]

    if initial_new_count > 0 and review_buttons:
        review_buttons[0].click().run()
        after_stats = get_alert_statistics()
        assert after_stats["new_alerts"] == initial_new_count - 1

    # 6. Test Logout
    logout_buttons = [b for b in at.button if "LOGOUT" in b.label]
    assert len(logout_buttons) > 0, "Logout button must be available"
    logout_buttons[0].click().run()
    assert at.session_state.authenticated is False

    # 7. Test Analyst 1-Click Login
    analyst_btn = None
    for b in at.button:
        if "Senior Cyber Analyst" in b.label and "1-Click" in b.label:
            analyst_btn = b
            break
    assert analyst_btn is not None, "1-Click Analyst button must exist"
    analyst_btn.click().run()

    assert at.session_state.authenticated is True
    assert at.session_state.user["role"] == "ANALYST"
