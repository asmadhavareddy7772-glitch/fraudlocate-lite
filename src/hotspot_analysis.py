"""
FraudLocate Lite - Cluster Statistics & Patrol Coverage Priority Ranking.
Computes descriptive cluster metrics and historical hotspot coverage scores.

IMPORTANT ETHICAL SAFEGUARD:
This scoring reflects HISTORICAL withdrawal density and resource distribution.
It is an operational patrol coverage priority index for decision support,
NOT a probabilistic prediction of future criminal acts or targets.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from src.clustering import NOISE_LABEL_STR


def compute_cluster_statistics(
    df: pd.DataFrame,
    cluster_centroids: Optional[Dict[int, tuple[float, float]]] = None,
    cluster_radii_km: Optional[Dict[int, float]] = None,
) -> pd.DataFrame:
    """
    Calculate comprehensive descriptive statistics for each DBSCAN cluster.

    Args:
        df: DataFrame with 'cluster_id' and transaction fields.
        cluster_centroids: Dict mapping cluster_id -> (lat, lon).
        cluster_radii_km: Dict mapping cluster_id -> radius in km.

    Returns:
        DataFrame with one row per cluster (sorted by cluster_id).
    """
    if "cluster_id" not in df.columns:
        raise ValueError("DataFrame must contain 'cluster_id' column.")

    total_dataset_txns = len(df)
    unique_clusters = sorted([c for c in df["cluster_id"].unique() if c != -1])

    if not unique_clusters:
        return pd.DataFrame()

    if cluster_centroids is None:
        cluster_centroids = {}
        for c in unique_clusters:
            c_pts = df[df["cluster_id"] == c]
            cluster_centroids[c] = (float(c_pts["latitude"].mean()), float(c_pts["longitude"].mean()))

    if cluster_radii_km is None:
        cluster_radii_km = {}
        for c in unique_clusters:
            cluster_radii_km[c] = 0.5

    # Timeframe boundaries for recency calculation
    df_sorted = df.copy()
    if "date" in df.columns:
        df_sorted["dt_calc"] = pd.to_datetime(df_sorted["date"] + " " + df_sorted.get("time", "12:00:00"))
        max_time = df_sorted["dt_calc"].max()
        min_time = df_sorted["dt_calc"].min()
        total_time_span = max((max_time - min_time).total_seconds(), 1.0)
    else:
        df_sorted["dt_calc"] = None
        max_time, min_time, total_time_span = None, None, 1.0

    cluster_rows = []

    for c in unique_clusters:
        pts = df_sorted[df_sorted["cluster_id"] == c]
        txn_count = len(pts)
        num_atms = pts["atm_id"].nunique()
        total_amount = float(pts["withdrawal_amount"].sum())
        avg_amount = float(pts["withdrawal_amount"].mean())
        max_amount = float(pts["withdrawal_amount"].max())
        pct_txns = round((txn_count / total_dataset_txns * 100.0), 2) if total_dataset_txns > 0 else 0.0

        # Peak temporal windows
        peak_hour = int(pts["hour"].mode()[0]) if not pts["hour"].empty else 14
        peak_day = str(pts["day_of_week"].mode()[0]) if not pts["day_of_week"].empty else "N/A"

        # Most representative area name
        primary_area = str(pts["area"].mode()[0]) if not pts["area"].empty else "Unknown Zone"

        # Centroid & Radius
        centroid = cluster_centroids.get(c, (float(pts["latitude"].mean()), float(pts["longitude"].mean())))
        radius = cluster_radii_km.get(c, 0.5)

        # Recency score: transactions occurring in recent 35% time window
        if max_time is not None and min_time is not None:
            recent_cutoff = max_time - pd.Timedelta(seconds=total_time_span * 0.35)
            recent_txns = int((pts["dt_calc"] >= recent_cutoff).sum())
            recency_ratio = float(recent_txns / txn_count) if txn_count > 0 else 0.0
        else:
            recency_ratio = 0.5

        top_atms = pts["atm_name"].value_counts().head(3).index.tolist()

        cluster_rows.append({
            "cluster_id": c,
            "cluster_label": f"Cluster {c}",
            "primary_area": primary_area,
            "num_withdrawals": txn_count,
            "num_unique_atms": num_atms,
            "total_withdrawal_amount": total_amount,
            "avg_withdrawal_amount": round(avg_amount, 2),
            "max_withdrawal_amount": max_amount,
            "pct_of_total_withdrawals": pct_txns,
            "most_active_hour": peak_hour,
            "most_active_hour_str": f"{peak_hour:02d}:00 - {(peak_hour+1)%24:02d}:00",
            "most_active_day": peak_day,
            "centroid_lat": centroid[0],
            "centroid_lon": centroid[1],
            "approx_radius_km": radius,
            "recency_ratio": recency_ratio,
            "top_atms": top_atms,
        })

    return pd.DataFrame(cluster_rows)


def rank_hotspots(
    cluster_stats_df: pd.DataFrame,
    w_count: float = 0.40,
    w_atms: float = 0.20,
    w_amount: float = 0.20,
    w_recent: float = 0.20,
) -> pd.DataFrame:
    """
    Compute transparent Patrol Coverage Priority Score for each hotspot.

    Formula:
    Priority Score (0-100) = 100 * [
        w_count * Norm(Withdrawal Count) +
        w_atms * Norm(Unique ATMs) +
        w_amount * Norm(Total Amount) +
        w_recent * Norm(Recency Ratio)
    ]

    Args:
        cluster_stats_df: Cluster statistics computed via compute_cluster_statistics.
        w_count: Weight for withdrawal volume (default: 0.4).
        w_atms: Weight for unique ATM kiosks involved (default: 0.2).
        w_amount: Weight for total money withdrawn (default: 0.2).
        w_recent: Weight for historical recency (default: 0.2).

    Returns:
        DataFrame sorted descending by priority score with assigned priority tiers.
    """
    if cluster_stats_df.empty:
        return cluster_stats_df

    df_ranked = cluster_stats_df.copy()

    # Min-max normalization helper
    def min_max_norm(series: pd.Series) -> pd.Series:
        s_min = series.min()
        s_max = series.max()
        if s_max == s_min:
            return pd.Series(1.0, index=series.index)
        return (series - s_min) / (s_max - s_min)

    norm_count = min_max_norm(df_ranked["num_withdrawals"])
    norm_atms = min_max_norm(df_ranked["num_unique_atms"])
    norm_amount = min_max_norm(df_ranked["total_withdrawal_amount"])
    norm_recent = min_max_norm(df_ranked["recency_ratio"])

    # Ensure weights sum to 1.0
    weight_sum = w_count + w_atms + w_amount + w_recent
    if weight_sum <= 0:
        w_count, w_atms, w_amount, w_recent = 0.4, 0.2, 0.2, 0.2
        weight_sum = 1.0

    c_w = w_count / weight_sum
    a_w = w_atms / weight_sum
    m_w = w_amount / weight_sum
    r_w = w_recent / weight_sum

    raw_score = (
        c_w * norm_count
        + a_w * norm_atms
        + m_w * norm_amount
        + r_w * norm_recent
    )

    df_ranked["priority_score"] = (raw_score * 100.0).round(1)

    # Assign operational patrol priority tiers
    def assign_tier(score: float) -> str:
        if score >= 70.0:
            return "High Priority"
        elif score >= 40.0:
            return "Medium Priority"
        else:
            return "Low Priority"

    df_ranked["priority_tier"] = df_ranked["priority_score"].apply(assign_tier)
    df_ranked["ranking"] = df_ranked["priority_score"].rank(ascending=False, method="min").astype(int)

    df_ranked = df_ranked.sort_values(by="priority_score", ascending=False).reset_index(drop=True)
    return df_ranked
