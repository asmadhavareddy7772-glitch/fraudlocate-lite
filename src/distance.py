"""
FraudLocate Lite - Distance & Travel Time Calculations Module.
Provides accurate spherical Haversine calculations and patrol travel time estimates.
"""

import math
from typing import Tuple, List, Dict, Union, Any
import numpy as np

# Standard Earth radius in kilometers (IUGG mean radius)
EARTH_RADIUS_KM = 6371.0088

TRAVEL_TIME_DISCLAIMER = (
    "Travel time is an estimate and does not account for real-time traffic, "
    "road restrictions, signals, or emergency conditions."
)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth using the Haversine formula.

    Args:
        lat1: Latitude of point 1 in decimal degrees.
        lon1: Longitude of point 1 in decimal degrees.
        lat2: Latitude of point 2 in decimal degrees.
        lon2: Longitude of point 2 in decimal degrees.

    Returns:
        Distance in kilometers (rounded to 3 decimal places).
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    # Clip to avoid floating point precision out-of-range issues in asin/sqrt
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(EARTH_RADIUS_KM * c, 3)


def haversine_distance_matrix(coords: List[Tuple[float, float]]) -> np.ndarray:
    """
    Compute full pairwise Haversine distance matrix (in km) for a list of (lat, lon) coordinates.

    Args:
        coords: List of (lat, lon) tuples in decimal degrees.

    Returns:
        N x N symmetric matrix of distances in km.
    """
    n = len(coords)
    matrix = np.zeros((n, n), dtype=float)
    if n <= 1:
        return matrix

    # Convert to radians
    coords_rad = np.radians(coords)
    lats = coords_rad[:, 0]
    lons = coords_rad[:, 1]

    for i in range(n):
        d_lat = lats[i:] - lats[i]
        d_lon = lons[i:] - lons[i]
        a = (
            np.sin(d_lat / 2.0) ** 2
            + np.cos(lats[i]) * np.cos(lats[i:]) * np.sin(d_lon / 2.0) ** 2
        )
        a = np.clip(a, 0.0, 1.0)
        c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
        dists = EARTH_RADIUS_KM * c

        matrix[i, i:] = dists
        matrix[i:, i] = dists

    return np.round(matrix, 3)


def calculate_travel_time(distance_km: float, speed_kmh: float = 30.0) -> Dict[str, Union[float, str]]:
    """
    Calculate estimated travel time between locations given distance and average patrol speed.

    Args:
        distance_km: Distance traveled in kilometers.
        speed_kmh: Patrol speed in km/h (default 30 km/h).

    Returns:
        Dict with keys:
            - 'distance_km': float
            - 'speed_kmh': float
            - 'time_hours': float
            - 'time_minutes': float
            - 'formatted_time': str (e.g., '14 mins' or '1 hr 12 mins')
            - 'disclaimer': str
    """
    if speed_kmh <= 0:
        raise ValueError("Patrol speed must be greater than zero.")

    time_hours = distance_km / speed_kmh
    time_minutes = time_hours * 60.0

    if time_minutes < 1.0:
        formatted = f"{int(round(time_minutes * 60))} sec" if time_minutes > 0 else "0 min"
    elif time_minutes < 60.0:
        formatted = f"{round(time_minutes, 1)} mins"
    else:
        hrs = int(time_minutes // 60)
        mins = int(round(time_minutes % 60))
        formatted = f"{hrs} hr {mins} mins" if mins > 0 else f"{hrs} hr"

    return {
        "distance_km": round(distance_km, 2),
        "speed_kmh": round(speed_kmh, 1),
        "time_hours": round(time_hours, 3),
        "time_minutes": round(time_minutes, 1),
        "formatted_time": formatted,
        "disclaimer": TRAVEL_TIME_DISCLAIMER,
    }


def is_valid_coordinates(lat: Any, lon: Any) -> bool:
    """Validate that coordinates are numeric and within valid geographic bounds (-90..90, -180..180)."""
    try:
        f_lat = float(lat)
        f_lon = float(lon)
        return -90.0 <= f_lat <= 90.0 and -180.0 <= f_lon <= 180.0
    except (TypeError, ValueError):
        return False

