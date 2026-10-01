# FraudLocate Lite — Cyber-Fraud Withdrawal Hotspot & Patrol Coverage Analytics

**Problem Statement ID:** PS-024  
**Domain:** Data Science & Predictive Analytics  
**Scope:** Reviewer Feedback Implementation — Real-Time Evidence Intake, Dual Police Alerting, Incident Timelines & Geospatial Patrol Coverage

---

## 🛡️ Executive Summary

Cyber fraud syndicates frequently deploy decentralized networks of **money mules** who make rapid cash withdrawals at automated teller machines (ATMs) across urban corridors immediately following unauthorized bank transfers. Local police patrols face significant coverage challenges across hundreds of scattered kiosk locations.

**FraudLocate Lite** delivers an operational end-to-end incident response decision-support system:
1. **Fraud Evidence Input:** Supports uploaded images (ATM photographs, CCTV/vestibule screenshots) and video clips (CCTV camera recordings), alongside one-click synthetic demo presets. Generates standardized IDs (e.g. `EVD-2026-00125`).
2. **Fraud Detection & Latency Benchmark:** Automated pipeline that inspects media metadata, correlates ATM locations with historical withdrawal density and active DBSCAN hotspot clusters, and measures processing latency.
3. **Real-Time Dual Police Notification:**
   - **In-App Police Dashboard (Laptop 2):** Real-time alert feed with status lifecycle (`New`, `Acknowledged`, `Under Review`, `Resolved`), tactical location mapping, historical ATM activity, hotspot context, and patrol unit dispatch simulation.
   - **Email Notification:** Generates standardized HTML alert emails sent via SMTP or demonstrated via **Demo Email Mode** with full rendered preview and dispatch audit logs.
4. **Chronological Incident Timeline:** Exact millisecond timestamps across all 7 operational stages:
   `Evidence Uploaded` → `Evidence Processed` → `Fraud Event Created` → `Alert Generated` → `Police Notified` → `Alert Reviewed` → `Case Status Updated`.
5. **DBSCAN Geospatial Clustering:** Spherical Haversine metric on Earth radians for geodesic cluster boundaries and noise isolation.
6. **Heuristic Patrol Route Planning:** Nearest-Neighbor algorithm providing sequential turn-by-turn waypoint schedules, leg distances, and travel times from Police Command Headquarters.
7. **One-Click Rapid Demo Mode:** A single-click **"🚀 Simulate Fraud Event"** button executes the entire end-to-end workflow in seconds for live presentations.

> [!IMPORTANT]
> **Ethical & Scope Safeguard**: *"FraudLocate Lite is a synthetic-data decision-support prototype developed for academic and demonstration purposes."*
> Historical withdrawal concentration does NOT imply guaranteed future criminal activity or individual wrongdoing.
> Route suggestions are heuristic planning aids and do NOT guarantee criminal interception.
> The platform does not connect to real-world live CCTV feeds, cellular tracking, wiretapping, or banking core databases.

---

## 📸 Complete System Workflow

```
[ANALYST LAPTOP]                                      [POLICE LAPTOP]
Upload Image / Video
        |
        v
"Analyze Evidence"
        |
        v
Evidence Received
        |
        v
Processing & Metadata Extraction
        |
        v
Analysis Completed (Terminology: Potential Fraud Event)
        |
        v
Fraud Event Created
        |
        v
Police Alert Generated (ALERT-XXXXX, Status: NEW)
        |
   +----+-----------------------------+
   |                                  |
   v                                  v
In-App SQLite Notification       Email Alert (Live / Demo Mode)
   |                                  |
   +----------------+-----------------+
                    |
                    v
          New Alert Appears (Police Dashboard)
                    |
                    v
          Officer Opens Alert
                    |
         +----------+----------+----------+
         |          |          |          |
         v          v          v          v
    View Evid.  View ATM   View Hotspot  View Patrol
         |          |          |          |
         v          v          v          v
     Preview    Tactical     DBSCAN    Nearest-Neighbor
     CCTV       Location     Cluster   Route Schedule
     Image/Vid  Map          Bounds    (Travel Time)
                    |
                    v
          "Mark as Reviewed" / Acknowledge
                    |
                    v
          Update Status: Under Review / Resolved
```

---

## 🧭 Structured System Navigation

The dashboard provides a hierarchical navigation structure:

```
Dashboard
  - Overview & KPIs
Fraud Evidence
  - Upload Evidence
  - Evidence History
Fraud Detection
  - Analyze Evidence
  - Detection Results
Police Alerts
  - New Alerts
  - Alert History
  - Alert Details
Geospatial Intelligence
  - ATM Map
  - DBSCAN Hotspots
  - Historical Activity
Patrol Planning
  - Priority Hotspots
  - Route Recommendation
Reports
  - Incident Report
  - Alert Report
  - Evidence Report
Methodology
  - Architecture
  - Algorithms
  - Data Flow
  - Privacy & Ethics
```

---

## 💻 Two-Laptop Hackathon Demonstration Guide

### Step 1: Terminal Setup

- **Laptop 1 (Analyst Laptop):**
  Open `http://localhost:8501/` (or your local network IP `http://<laptop-1-ip>:8501/`).
  Navigate to **Fraud Evidence → Upload Evidence**.

- **Laptop 2 (Police Dashboard Laptop):**
  Open `http://<laptop-1-ip>:8501/?view=police` or select **Police Alerts** in the sidebar.

---

### Step 2: Demonstration Sequence (3–5 Minutes)

#### A. Standard Workflow
1. **On Laptop 1 (Analyst):**
   - In **Fraud Evidence → Upload Evidence**, select a sample preset (`📷 CCTV 1 (Day)` or `🎥 CCTV Clip`).
   - Notice the extracted metadata: resolution, file size, ATM correlation (`ATM_HYD_102` in Ameerpet).
   - Click **"🚀 Analyze Evidence"**.
   - Observe the 5-step detection tracker and latency benchmark (e.g. `0.28s`).
   - Alert `ALERT-XXXXX` is generated and saved to SQLite with status `New`.

2. **On Laptop 2 (Police Terminal):**
   - The red notification banner updates: **"🚨 1 New Incident Alert(s)"**.
   - In **Police Alerts → Alert Details**, the officer opens the alert.
   - The 7-step incident timeline shows exact timestamps.
   - The officer clicks the 4 connected action buttons:
     - **[🔍 View Evidence]**: Inspects high-resolution CCTV image or video player.
     - **[📍 View ATM on Map]**: Centers the tactical map on the target kiosk and shows dispatch vector from Police HQ.
     - **[🎯 View Hotspot Cluster]**: Shows DBSCAN cluster boundary, centroid, and priority score.
     - **[🚔 View Patrol Route]**: Inspects the suggested patrol coverage schedule and travel time.
   - The officer selects **"Acknowledged"** or **"Under Review"**, enters notes, and clicks **"💾 Update Status & Save Notes"**.

#### B. Rapid 30-Second Demonstration (One-Click Demo Mode)
- Click the prominent **"🚀 Simulate Fraud Event"** button at the top of the sidebar.
- The system automatically selects a synthetic ATM, pairs sample evidence, executes analysis, triggers dual alerts, and opens the alert dossier in the Police Dashboard ready for review!

---

## 🛠️ Technology Stack & Storage

- **Core Framework:** Python 3.12, Streamlit 1.64
- **Geospatial Engine:** Scikit-learn (DBSCAN with `metric='haversine'`), SciPy
- **Mapping & Visuals:** Folium 0.15, Streamlit-Folium, Plotly Express & Graph Objects
- **Data & Computations:** Pandas, NumPy
- **Computer Vision & Media:** OpenCV (`cv2`), Pillow (`PIL`)
- **Alert Persistence:** Local SQLite database (`data/alerts.db`) with status lifecycle and timeline JSON
- **Notification Engine:** Standard Python `smtplib` and `email.mime` with environment variable configuration and zero-config **Demo Email Mode**

---

## 🔬 Automated Test Suite

FraudLocate Lite includes 27 automated unit and integration tests:

```bash
python -m pytest -v
```

```
tests/test_core.py::TestDistanceCalculations::test_haversine_known_points PASSED
tests/test_core.py::TestDistanceCalculations::test_haversine_zero_distance PASSED
tests/test_core.py::TestDistanceCalculations::test_haversine_matrix PASSED
tests/test_core.py::TestDistanceCalculations::test_travel_time_calculation PASSED
tests/test_core.py::TestDataGenerationAndCleaning::test_generate_synthetic_dataset PASSED
tests/test_core.py::TestDataGenerationAndCleaning::test_preprocessing_valid_records PASSED
tests/test_core.py::TestDataGenerationAndCleaning::test_preprocessing_filters_invalid_data PASSED
tests/test_core.py::TestClusteringAndRanking::test_dbscan_clustering_identifies_clusters PASSED
tests/test_core.py::TestClusteringAndRanking::test_compute_cluster_statistics PASSED
tests/test_core.py::TestPatrolRouteOptimizer::test_patrol_route_optimizer PASSED
tests/test_evidence_and_alerts.py::TestIdentifiersAndMetadata::test_generate_evidence_id PASSED
tests/test_evidence_and_alerts.py::TestIdentifiersAndMetadata::test_generate_case_id PASSED
tests/test_evidence_and_alerts.py::TestIdentifiersAndMetadata::test_generate_alert_id PASSED
tests/test_evidence_and_alerts.py::TestIdentifiersAndMetadata::test_extract_image_metadata PASSED
tests/test_evidence_and_alerts.py::TestIdentifiersAndMetadata::test_extract_video_metadata PASSED
tests/test_evidence_and_alerts.py::TestAlertStoreCRUDAndStatus::test_insert_and_retrieve_alert PASSED
tests/test_evidence_and_alerts.py::TestAlertStoreCRUDAndStatus::test_lifecycle_status_transitions PASSED
tests/test_evidence_and_alerts.py::TestAlertStoreCRUDAndStatus::test_alert_statistics_kpis PASSED
tests/test_evidence_and_alerts.py::TestNotificationService::test_format_alert_email_html PASSED
tests/test_evidence_and_alerts.py::TestNotificationService::test_send_fraud_alert_email_demo_mode PASSED
tests/test_evidence_and_alerts.py::TestHotspotCorrelationAndEndToEnd::test_hotspot_correlation PASSED
tests/test_evidence_and_alerts.py::TestHotspotCorrelationAndEndToEnd::test_complete_end_to_end_pipeline_with_timeline PASSED
tests/test_evidence_and_alerts.py::TestHotspotCorrelationAndEndToEnd::test_one_click_simulate_fraud_event PASSED
tests/test_evidence_and_alerts.py::TestReportsGeneration::test_generate_incident_report PASSED
tests/test_evidence_and_alerts.py::TestReportsGeneration::test_generate_alert_report PASSED
tests/test_evidence_and_alerts.py::TestReportsGeneration::test_generate_evidence_report PASSED
tests/test_evidence_and_alerts.py::TestReportsGeneration::test_generate_executive_briefing PASSED

============================= 27 passed in 6.32s =============================
```

---

## ⚖️ Standardized Ethical Terminology

In accordance with responsible data science principles:

### Standardized Terminology:
- ✅ *"Potential Fraud Event"*
- ✅ *"Fraud Evidence"*
- ✅ *"Evidence Analysis"*
- ✅ *"Suspicious Activity"*
- ✅ *"Analysis Completed"*
- ✅ *"Patrol Coverage Recommendation"*

### Strict Prohibitions:
- ❌ *"Criminal Identified"*
- ❌ *"Criminal Located"*
- ❌ *"Guaranteed Fraud"*
- ❌ *"Guaranteed Interception"*
- ❌ *"Predictive Arrest Guarantee"*

---

## 📜 License & Compliance

Developed for **Problem Statement PS-024 (Data Science & Predictive Analytics)**.  
For educational, academic research, and simulated patrol-planning decision-support demonstrations only.
