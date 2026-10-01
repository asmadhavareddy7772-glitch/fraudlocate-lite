"""
FraudLocate Lite - DBSCAN Geospatial Hotspot Engine.
Executes density-based spatial clustering using spherical Haversine metric on radians.
"""

from typing import Tuple, Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from src.distance import EARTH_RADIUS_KM, haversine_distance_km

NOISE_LABEL_STR = "Noise / Unclustered"


def run_dbscan_clustering(
    df: pd.DataFrame,
    radius_km: float = 1.0,
    min_samples: int = 5,
    eps_km: Optional[float] = None,
    **kwargs,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Run DBSCAN clustering with Haversine metric on geographic coordinates.

    Args:
        df: Preprocessed DataFrame containing 'latitude', 'longitude' columns.
        radius_km: Neighborhood radius (epsilon) in kilometers.
        min_samples: Minimum points required to form a dense cluster.
        eps_km: Alias for radius_km.

    Returns:
        (df_clustered, cluster_summary)
        where df_clustered contains 'cluster_id' and 'cluster_label'.
    """
    if eps_km is not None:
        radius_km = eps_km
    if len(df) == 0:
        empty_summary = {
            "num_clusters": 0,
            "num_noise": 0,
            "noise_percentage": 0.0,
            "radius_km": radius_km,
            "min_samples": min_samples,
            "cluster_centroids": {},
            "cluster_radii_km": {},
            "cluster_ids": [],
        }
        df_empty = df.copy()
        df_empty["cluster_id"] = []
        df_empty["cluster_label"] = []
        return df_empty, empty_summary

    # Ensure radius is strictly positive
    radius_km = max(0.05, float(radius_km))
    min_samples = max(2, int(min_samples))

    # Convert geographic distance (km) to radians on Earth sphere
    eps_radians = radius_km / EARTH_RADIUS_KM

    # Extract coordinates in radians (Latitude first, Longitude second)
    coords_rad = np.radians(df[["latitude", "longitude"]].values)

    # Scikit-learn DBSCAN with metric='haversine' and algorithm='ball_tree'
    db = DBSCAN(
        eps=eps_radians,
        min_samples=min_samples,
        metric="haversine",
        algorithm="ball_tree"
    )
    cluster_labels = db.fit_predict(coords_rad)

    df_out = df.copy()
    df_out["cluster_id"] = cluster_labels
    df_out["cluster_label"] = [
        f"Cluster {c}" if c != -1 else NOISE_LABEL_STR
        for c in cluster_labels
    ]

    # Analyze clusters
    unique_clusters = sorted([c for c in set(cluster_labels) if c != -1])
    num_clusters = len(unique_clusters)
    num_noise = int(np.sum(cluster_labels == -1))
    noise_pct = round((num_noise / len(df) * 100.0), 2) if len(df) > 0 else 0.0

    cluster_centroids: Dict[int, Tuple[float, float]] = {}
    cluster_radii_km: Dict[int, float] = {}

    for c in unique_clusters:
        pts = df_out[df_out["cluster_id"] == c]
        # Centroid calculated as geographic mean of lat and lon
        c_lat = float(pts["latitude"].mean())
        c_lon = float(pts["longitude"].mean())
        cluster_centroids[c] = (round(c_lat, 6), round(c_lon, 6))

        # Approximate radius: maximum haversine distance from centroid to any point in the cluster
        dists = [
            haversine_distance_km(c_lat, c_lon, row["latitude"], row["longitude"])
            for _, row in pts.iterrows()
        ]
        approx_radius = max(dists) if dists else 0.05
        # Guard against zero radius (e.g. all points at identical ATM)
        cluster_radii_km[c] = max(0.10, round(approx_radius, 3))

    summary: Dict[str, Any] = {
        "num_clusters": num_clusters,
        "num_noise": num_noise,
        "noise_percentage": noise_pct,
        "radius_km": radius_km,
        "min_samples": min_samples,
        "cluster_centroids": cluster_centroids,
        "cluster_radii_km": cluster_radii_km,
        "cluster_ids": unique_clusters,
    }

    return df_out, summary
