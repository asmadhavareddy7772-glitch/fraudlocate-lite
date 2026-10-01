"""
FraudLocate Lite - Fraud Evidence Processing & Intelligence Pipeline.
Accepts synthetic/sample image and video evidence, performs metadata extraction,
risk indicator evaluation, ATM location correlation, DBSCAN hotspot association,
builds complete 7-stage incident timelines, and immediately triggers police alerting.

ETHICAL SAFEGUARD:
Uses objective, descriptive terminology:
- "Potential Fraud Event"
- "Fraud Evidence"
- "Evidence Analysis"
- "Suspicious Activity"
- "Analysis Completed"
Strictly avoids predictive criminal identification or certainty claims.
"""

import os
import time
import random
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from PIL import Image

from src.distance import haversine_distance_km, calculate_travel_time
from src.alert_store import insert_alert, generate_alert_id
from src.notification_service import send_fraud_alert_email, generate_google_maps_link
from src.route_optimizer import DEFAULT_HQ_COORDS, build_nearest_neighbor_patrol_route
from utils.sample_evidence_generator import SAMPLE_DIR, ensure_sample_evidence_exists

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")


def generate_evidence_id(prefix: str = "EVD") -> str:
    """Generate a standardized Evidence Identifier in EVD-YYYY-XXXXX format."""
    now = datetime.now()
    rand_suffix = random.randint(10000, 99999)
    return f"{prefix}-{now.strftime('%Y')}-{rand_suffix}"


def generate_case_id(prefix: str = "CASE") -> str:
    """Generate a standardized Complaint/Case Identifier in CASE-YYYY-XXXXX format."""
    now = datetime.now()
    case_num = random.randint(10000, 99999)
    return f"{prefix}-{now.strftime('%Y')}-{case_num}"


def save_uploaded_evidence(
    uploaded_file,
    evidence_id: str,
) -> str:
    """Save user-uploaded file to local data/uploads/ directory."""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    orig_name = getattr(uploaded_file, "name", "uploaded_file.bin")
    _, ext = os.path.splitext(orig_name)
    target_filename = f"{evidence_id}{ext}"
    target_path = os.path.join(UPLOADS_DIR, target_filename)

    with open(target_path, "wb") as f:
        if hasattr(uploaded_file, "getbuffer"):
            f.write(uploaded_file.getbuffer())
        elif hasattr(uploaded_file, "read"):
            f.write(uploaded_file.read())
        else:
            shutil.copyfile(uploaded_file, target_path)

    return target_path


def extract_media_metadata(file_path: str) -> Dict[str, Any]:
    """Extract technical and forensic metadata from image or video file."""
    if not os.path.exists(file_path):
        return {"error": "File not found", "file_size_kb": 0, "media_type": "Image"}

    size_bytes = os.path.getsize(file_path)
    size_kb = round(size_bytes / 1024, 2)
    _, ext = os.path.splitext(file_path)
    ext = ext.lower().replace(".", "")
    is_video = ext in ["mp4", "avi", "mov", "mkv", "webm"]

    metadata: Dict[str, Any] = {
        "file_name": os.path.basename(file_path),
        "file_path": file_path,
        "extension": ext,
        "media_type": "Video" if is_video else "Image",
        "file_size_kb": size_kb,
        "timestamp_analyzed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if not is_video:
        try:
            with Image.open(file_path) as img:
                metadata["width"] = img.width
                metadata["height"] = img.height
                metadata["aspect_ratio"] = f"{img.width}:{img.height}"
                metadata["color_mode"] = img.mode
                metadata["format"] = img.format or ext.upper()
        except Exception as e:
            metadata["image_error"] = str(e)
            metadata["width"] = 720
            metadata["height"] = 480
    else:
        try:
            import cv2
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                metadata["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                metadata["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                metadata["fps"] = round(cap.get(cv2.CAP_PROP_FPS), 2)
                metadata["total_frames"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if metadata["fps"] > 0:
                    metadata["duration_seconds"] = round(metadata["total_frames"] / metadata["fps"], 2)
                else:
                    metadata["duration_seconds"] = 3.0
                cap.release()
        except Exception as e:
            metadata["video_error"] = str(e)
            metadata["duration_seconds"] = 3.0
            metadata["width"] = 640
            metadata["height"] = 480

    return metadata


def correlate_atm_with_hotspots(
    atm_id: str,
    atm_lat: float,
    atm_lon: float,
    ranked_hotspots_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Check if the specified ATM coordinates fall within any active DBSCAN hotspot cluster."""
    if ranked_hotspots_df is None or ranked_hotspots_df.empty:
        return {
            "is_in_hotspot": False,
            "cluster_id": -1,
            "hotspot_score": 0.0,
            "cluster_label": "Unclustered / Background Noise",
            "distance_to_centroid_km": None,
            "approx_radius_km": None,
            "priority_tier": "Normal / Unclustered",
        }

    closest_cluster = None
    min_dist = float("inf")

    for _, c_row in ranked_hotspots_df.iterrows():
        c_lat = float(c_row["centroid_lat"])
        c_lon = float(c_row["centroid_lon"])
        dist_km = haversine_distance_km(atm_lat, atm_lon, c_lat, c_lon)
        radius_km = float(c_row.get("approx_radius_km", 0.5))

        if dist_km <= radius_km:
            return {
                "is_in_hotspot": True,
                "cluster_id": int(c_row["cluster_id"]),
                "hotspot_score": float(c_row.get("priority_score", 0.0)),
                "cluster_label": str(c_row.get("cluster_label", f"Cluster {int(c_row['cluster_id'])}")),
                "primary_area": str(c_row.get("primary_area", "Area")),
                "distance_to_centroid_km": round(dist_km, 3),
                "approx_radius_km": radius_km,
                "priority_tier": str(c_row.get("priority_tier", "High Priority")),
            }

        if dist_km < min_dist:
            min_dist = dist_km
            closest_cluster = c_row

    if closest_cluster is not None:
        return {
            "is_in_hotspot": False,
            "cluster_id": int(closest_cluster["cluster_id"]),
            "hotspot_score": float(closest_cluster.get("priority_score", 0.0)),
            "cluster_label": str(closest_cluster.get("cluster_label", f"Cluster {int(closest_cluster['cluster_id'])}")),
            "primary_area": str(closest_cluster.get("primary_area", "Area")),
            "distance_to_centroid_km": round(min_dist, 3),
            "approx_radius_km": float(closest_cluster.get("approx_radius_km", 0.5)),
            "priority_tier": f"Near {closest_cluster.get('cluster_label')} ({min_dist:.2f} km)",
        }

    return {
        "is_in_hotspot": False,
        "cluster_id": -1,
        "hotspot_score": 0.0,
        "cluster_label": "Unclustered Kiosk",
        "distance_to_centroid_km": None,
        "approx_radius_km": None,
        "priority_tier": "Normal / Unclustered",
    }


def process_fraud_evidence(
    file_path: str,
    atm_info: Dict[str, Any],
    complaint_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
    flagged_amount: float = 25000.0,
    ranked_hotspots_df: Optional[pd.DataFrame] = None,
    historical_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Complete end-to-end evidence processing workflow:
    1. Records timestamps & benchmarks execution latency.
    2. Builds complete 7-stage incident timeline.
    3. Extracts technical/forensic metadata.
    4. Evaluates historical activity around ATM.
    5. Correlates with DBSCAN hotspots.
    6. Formulates structured intelligence findings.
    7. Creates persistent alert in SQLite with status 'New'.
    8. Dispatches email notification (SMTP / Demo Mode).
    """
    t_start = time.time()
    t_uploaded = datetime.now()

    if not evidence_id:
        evidence_id = generate_evidence_id()
    if not complaint_id:
        complaint_id = generate_case_id()

    # Step 1: Metadata extraction
    media_meta = extract_media_metadata(file_path)
    evidence_type = media_meta.get("media_type", "Image")

    t_processed = datetime.now()

    # Step 2: ATM & Hotspot correlation
    atm_id = atm_info.get("atm_id", "ATM_HYD_102")
    atm_name = atm_info.get("atm_name", "SBI / HDFC Kiosk")
    atm_lat = float(atm_info.get("latitude", 17.4389))
    atm_lon = float(atm_info.get("longitude", 78.4514))
    area = atm_info.get("area", "Ameerpet Commercial Hub")
    city = atm_info.get("city", "Hyderabad")

    hotspot_corr = correlate_atm_with_hotspots(
        atm_id=atm_id,
        atm_lat=atm_lat,
        atm_lon=atm_lon,
        ranked_hotspots_df=ranked_hotspots_df,
    )

    # Step 3: Historical withdrawal stats for this ATM
    atm_history_count = 0
    atm_history_total = 0.0
    if historical_df is not None and not historical_df.empty and "atm_id" in historical_df.columns:
        matching_txns = historical_df[historical_df["atm_id"] == atm_id]
        atm_history_count = len(matching_txns)
        atm_history_total = float(matching_txns["withdrawal_amount"].sum())

    # Step 4: Analytical risk scoring
    is_in_hotspot = hotspot_corr.get("is_in_hotspot", False)
    hotspot_score = hotspot_corr.get("hotspot_score", 0.0)

    if is_in_hotspot or hotspot_score >= 70.0:
        severity = "Critical Priority"
        recommended_action = (
            f"Immediate patrol coverage recommended. Dispatch nearest mobile patrol unit to "
            f"{atm_name} ({area}). Coordinate with bank nodal officer to preserve vestibule CCTV records."
        )
    elif hotspot_score >= 40.0 or atm_history_count > 15:
        severity = "High Priority"
        recommended_action = (
            f"Include {atm_id} ({area}) in active sector patrol loop. Review nearby kiosk activity "
            f"over the next 60 minutes."
        )
    else:
        severity = "Elevated Priority"
        recommended_action = (
            f"Log incident for temporal correlation. Verify transaction timestamps against 1930 reporting queue."
        )

    analysis_result = (
        f"Potential Fraud Event: Evidence analysis completed for {atm_id} ({area}). "
        f"Correlated with {hotspot_corr.get('cluster_label')}; "
        f"historical ATM withdrawal concentration: {atm_history_count} transactions (₹{atm_history_total/1e5:.1f} Lakhs). "
        f"Analysis Completed."
    )

    t_event_created = datetime.now()

    # Step 5: Construct Alert Record & Timeline
    alert_id = generate_alert_id()
    t_alert_gen = datetime.now()

    # Build 7-stage incident timeline with millisecond precision
    timeline = {
        "evidence_uploaded": t_uploaded.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "evidence_processed": t_processed.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "fraud_event_created": t_event_created.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "alert_generated": t_alert_gen.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "police_notified": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "alert_reviewed": None,
        "case_status_updated": None,
    }

    alert_payload = {
        "alert_id": alert_id,
        "evidence_id": evidence_id,
        "complaint_id": complaint_id,
        "timestamp": t_alert_gen.strftime("%Y-%m-%d %H:%M:%S"),
        "atm_id": atm_id,
        "atm_name": atm_name,
        "latitude": atm_lat,
        "longitude": atm_lon,
        "area": area,
        "city": city,
        "amount": flagged_amount,
        "evidence_type": evidence_type,
        "evidence_path": file_path,
        "analysis_result": analysis_result,
        "severity": severity,
        "detection_status": "Alert Generated",
        "recommended_action": recommended_action,
        "notification_status": "Pending Dispatch",
        "status": "New",
        "reviewed_status": "Unreviewed",
        "cluster_id": hotspot_corr.get("cluster_id", -1),
        "hotspot_score": hotspot_score,
        "map_link": generate_google_maps_link(atm_lat, atm_lon),
        "timeline": timeline,
        "extra_metadata": {
            "media": media_meta,
            "hotspot_correlation": hotspot_corr,
            "historical_withdrawals_at_atm": atm_history_count,
            "historical_amount_at_atm": atm_history_total,
        },
    }

    # Step 6: Store in SQLite
    inserted_id = insert_alert(alert_payload)

    # Step 7: Trigger Email Notification
    email_result = send_fraud_alert_email(alert_payload)
    t_notified = datetime.now()

    timeline["police_notified"] = t_notified.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    alert_payload["timeline"] = timeline
    alert_payload["notification_status"] = f"Sent ({email_result.get('mode', 'Demo')})"
    insert_alert(alert_payload)

    total_latency_seconds = round(time.time() - t_start, 3)

    return {
        "status": "SUCCESS",
        "alert_id": inserted_id,
        "evidence_id": evidence_id,
        "complaint_id": complaint_id,
        "map_link": generate_google_maps_link(atm_lat, atm_lon),
        "alert_data": alert_payload,
        "email_dispatch": email_result,
        "media_metadata": media_meta,
        "hotspot_correlation": hotspot_corr,
        "timeline": timeline,
        "historical_stats": {
            "atm_txn_count": atm_history_count,
            "atm_total_amount": atm_history_total,
        },
        "timing_pipeline": {
            "evidence_received": t_uploaded.strftime("%H:%M:%S.%f")[:-3],
            "processing": t_processed.strftime("%H:%M:%S.%f")[:-3],
            "analysis_completed": t_event_created.strftime("%H:%M:%S.%f")[:-3],
            "alert_generated": t_alert_gen.strftime("%H:%M:%S.%f")[:-3],
            "police_notified": t_notified.strftime("%H:%M:%S.%f")[:-3],
            "total_latency_seconds": total_latency_seconds,
        },
    }


def simulate_fraud_event(
    historical_df: pd.DataFrame,
    ranked_hotspots_df: Optional[pd.DataFrame] = None,
    sample_type: str = "Image",
) -> Dict[str, Any]:
    """
    ONE-CLICK DEMO MODE:
    Simulates the entire workflow in one go:
    1. Generates synthetic fraud event.
    2. Selects a synthetic ATM.
    3. Generates timestamps.
    4. Associates sample evidence.
    5. Runs analysis.
    6. Creates alert in SQLite.
    7. Updates police dashboard state.
    8. Generates demo email.
    9. Correlates ATM location on map.
    10. Attaches hotspot information.
    11. Formulates patrol coverage recommendation.
    """
    ensure_sample_evidence_exists()

    # Pre-select realistic sample evidence based on requested type
    if sample_type.lower() == "video":
        evidence_path = os.path.join(SAMPLE_DIR, "sample_cctv_clip.mp4")
        chosen_atm_id = "ATM_HYD_201"
        chosen_atm_name = "Kotak ATM - Cyber Towers Concourse"
        chosen_lat = 17.4486
        chosen_lon = 78.3908
        chosen_area = "Madhapur Tech Corridor"
        chosen_amount = 40000.0
    else:
        preset_choice = random.choice([1, 2])
        if preset_choice == 1:
            evidence_path = os.path.join(SAMPLE_DIR, "sample_cctv_1.jpg")
            chosen_atm_id = "ATM_HYD_102"
            chosen_atm_name = "HDFC 24x7 Cash Point - Maitrivanam"
            chosen_lat = 17.438924
            chosen_lon = 78.451465
            chosen_area = "Ameerpet Commercial Hub"
            chosen_amount = 25000.0
        else:
            evidence_path = os.path.join(SAMPLE_DIR, "sample_cctv_2.jpg")
            chosen_atm_id = "ATM_HYD_201"
            chosen_atm_name = "Kotak ATM - Cyber Towers Concourse"
            chosen_lat = 17.4486
            chosen_lon = 78.3908
            chosen_area = "Madhapur Tech Corridor"
            chosen_amount = 35000.0

    atm_info = {
        "atm_id": chosen_atm_id,
        "atm_name": chosen_atm_name,
        "latitude": chosen_lat,
        "longitude": chosen_lon,
        "area": chosen_area,
        "city": "Hyderabad",
    }

    complaint_id = generate_case_id()
    evidence_id = generate_evidence_id()

    # Process through pipeline
    result = process_fraud_evidence(
        file_path=evidence_path,
        atm_info=atm_info,
        complaint_id=complaint_id,
        evidence_id=evidence_id,
        flagged_amount=chosen_amount,
        ranked_hotspots_df=ranked_hotspots_df,
        historical_df=historical_df,
    )

    # Compute quick patrol route vector
    hq_lat = float(DEFAULT_HQ_COORDS["lat"])
    hq_lon = float(DEFAULT_HQ_COORDS["lon"])
    dist_to_hq = haversine_distance_km(hq_lat, hq_lon, chosen_lat, chosen_lon)
    travel_info = calculate_travel_time(dist_to_hq, speed_kmh=40.0)

    result["patrol_recommendation"] = {
        "distance_to_hq_km": round(dist_to_hq, 2),
        "estimated_travel_time": travel_info["formatted_time"],
        "recommended_unit": "Tiger-Patrol-1" if "Ameerpet" in chosen_area else "Falcon-Quick-Response-4",
        "action": f"Deploy nearest vehicle to {chosen_atm_name} ({chosen_area}). Target arrival: ~{travel_info['formatted_time']}.",
    }

    return result
