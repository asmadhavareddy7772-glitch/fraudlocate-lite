"""
FraudLocate Lite - Patrol Route Suggester Module.
Implements the Nearest-Neighbor Heuristic to generate sequential patrol coverage routes
across high-priority historical ATM withdrawal hotspots.

IMPORTANT ETHICAL & OPERATIONAL DISCLAIMER:
This route suggester uses a synthetic nearest-neighbor heuristic for simulated planning.
It is NOT a real-time navigation or criminal pursuit system. Travel times are idealized estimates
and do not account for real-world traffic, one-ways, police priority signals, or emergency situations.
"""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from src.distance import (
    haversine_distance_km,
    calculate_travel_time,
    TRAVEL_TIME_DISCLAIMER,
)

# Realistic Police Operational Headquarters default coordinate for Hyderabad
DEFAULT_HQ_COORDS = {
    "name": "Central Police Headquarters (Command Base)",
    "area": "Basheerbagh / Police Control Room",
    "lat": 17.3998,
    "lon": 78.4746,
}


def build_nearest_neighbor_patrol_route(
    hotspots_df: pd.DataFrame,
    start_point: Optional[Dict[str, Any]] = None,
    speed_kmh: float = 30.0,
    return_to_start: bool = True,
    top_n: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generate sequential patrol route using Nearest-Neighbor heuristic across selected hotspots.

    Args:
        hotspots_df: Ranked hotspots DataFrame (must contain centroid_lat, centroid_lon, cluster_id).
        start_point: Optional dict with 'name', 'lat', 'lon'. If None, starts from DEFAULT_HQ_COORDS.
        speed_kmh: Patrol vehicle speed in km/h (default: 30 km/h).
        return_to_start: Whether patrol returns to starting base at the end.
        top_n: If specified, restricts to top N ranked hotspots.

    Returns:
        Dict containing:
            - 'stops': List of stop dicts with turn-by-turn details
            - 'total_distance_km': float
            - 'estimated_travel_time': Dict (time in hours, minutes, formatted string)
            - 'waypoints_coords': List of (lat, lon) for polylines
            - 'summary_table': pd.DataFrame for UI display
            - 'disclaimer': str
    """
    if hotspots_df.empty:
        return {
            "stops": [],
            "total_distance_km": 0.0,
            "estimated_travel_time": calculate_travel_time(0.0, speed_kmh),
            "waypoints_coords": [],
            "summary_table": pd.DataFrame(),
            "disclaimer": TRAVEL_TIME_DISCLAIMER,
        }

    targets_df = hotspots_df.copy()
    if top_n is not None and top_n > 0:
        targets_df = targets_df.head(top_n)

    # Convert targets to candidate list
    unvisited: List[Dict[str, Any]] = []
    for _, row in targets_df.iterrows():
        c_id = int(row["cluster_id"])
        c_label = str(row.get("cluster_label", f"Cluster {c_id}"))
        area = str(row.get("primary_area", "Area"))
        score = float(row.get("priority_score", 0.0))
        tier = str(row.get("priority_tier", "Normal"))
        txns = int(row.get("num_withdrawals", 0))
        lat = float(row["centroid_lat"])
        lon = float(row["centroid_lon"])

        unvisited.append({
            "is_base": False,
            "cluster_id": c_id,
            "name": f"Hotspot #{c_id} ({area})",
            "cluster_label": c_label,
            "area": area,
            "priority_score": score,
            "priority_tier": tier,
            "transactions": txns,
            "lat": lat,
            "lon": lon,
        })

    # Set up starting point
    if start_point is None:
        start_point = DEFAULT_HQ_COORDS

    current_lat = float(start_point["lat"])
    current_lon = float(start_point["lon"])
    base_name = start_point.get("name", "Patrol Base")
    base_area = start_point.get("area", "Command Central")

    route_stops: List[Dict[str, Any]] = []
    waypoints_coords: List[Tuple[float, float]] = [(current_lat, current_lon)]

    # Stop 0: Base / Start
    route_stops.append({
        "stop_number": 0,
        "is_base": True,
        "name": f"Start: {base_name}",
        "area": base_area,
        "priority_score": "-",
        "priority_tier": "Origin Base",
        "transactions": "-",
        "lat": current_lat,
        "lon": current_lon,
        "leg_distance_km": 0.0,
        "cumulative_distance_km": 0.0,
        "leg_time_minutes": 0.0,
        "cumulative_time_minutes": 0.0,
    })

    total_dist_km = 0.0
    total_time_min = 0.0
    stop_idx = 1

    # Nearest Neighbor greedy traversal
    while unvisited:
        best_idx = -1
        min_dist = float("inf")

        for i, candidate in enumerate(unvisited):
            dist = haversine_distance_km(current_lat, current_lon, candidate["lat"], candidate["lon"])
            if dist < min_dist:
                min_dist = dist
                best_idx = i

        chosen = unvisited.pop(best_idx)
        leg_time_info = calculate_travel_time(min_dist, speed_kmh)
        leg_time_min = float(leg_time_info["time_minutes"])

        total_dist_km += min_dist
        total_time_min += leg_time_min

        current_lat = chosen["lat"]
        current_lon = chosen["lon"]
        waypoints_coords.append((current_lat, current_lon))

        route_stops.append({
            "stop_number": stop_idx,
            "is_base": False,
            "name": chosen["name"],
            "cluster_id": chosen["cluster_id"],
            "area": chosen["area"],
            "priority_score": chosen["priority_score"],
            "priority_tier": chosen["priority_tier"],
            "transactions": chosen["transactions"],
            "lat": current_lat,
            "lon": current_lon,
            "leg_distance_km": round(min_dist, 2),
            "cumulative_distance_km": round(total_dist_km, 2),
            "leg_time_minutes": round(leg_time_min, 1),
            "cumulative_time_minutes": round(total_time_min, 1),
        })
        stop_idx += 1

    # Optional return leg to origin base
    if return_to_start and len(route_stops) > 1:
        base_lat = float(start_point["lat"])
        base_lon = float(start_point["lon"])
        return_dist = haversine_distance_km(current_lat, current_lon, base_lat, base_lon)
        return_time_info = calculate_travel_time(return_dist, speed_kmh)
        return_time_min = float(return_time_info["time_minutes"])

        total_dist_km += return_dist
        total_time_min += return_time_min
        waypoints_coords.append((base_lat, base_lon))

        route_stops.append({
            "stop_number": stop_idx,
            "is_base": True,
            "name": f"Return: {base_name}",
            "area": base_area,
            "priority_score": "-",
            "priority_tier": "Base Return",
            "transactions": "-",
            "lat": base_lat,
            "lon": base_lon,
            "leg_distance_km": round(return_dist, 2),
            "cumulative_distance_km": round(total_dist_km, 2),
            "leg_time_minutes": round(return_time_min, 1),
            "cumulative_time_minutes": round(total_time_min, 1),
        })

    # Summary table for UI
    summary_rows = []
    for s in route_stops:
        summary_rows.append({
            "Stop #": s["stop_number"] if not s["is_base"] else ("Start" if s["stop_number"] == 0 else "End"),
            "Destination / Hotspot": s["name"],
            "Area": s["area"],
            "Priority": s["priority_tier"],
            "Withdrawals": s["transactions"],
            "Leg Dist (km)": f"{s['leg_distance_km']:.2f} km" if s["leg_distance_km"] > 0 else "-",
            "Total Dist (km)": f"{s['cumulative_distance_km']:.2f} km",
            "Leg Time": f"{s['leg_time_minutes']:.1f} min" if s["leg_time_minutes"] > 0 else "-",
            "Total Time": f"{s['cumulative_time_minutes']:.1f} min",
        })

    summary_table = pd.DataFrame(summary_rows)
    overall_time_dict = calculate_travel_time(total_dist_km, speed_kmh)

    return {
        "stops": route_stops,
        "total_distance_km": round(total_dist_km, 2),
        "estimated_travel_time": overall_time_dict,
        "waypoints_coords": waypoints_coords,
        "summary_table": summary_table,
        "disclaimer": TRAVEL_TIME_DISCLAIMER,
    }
