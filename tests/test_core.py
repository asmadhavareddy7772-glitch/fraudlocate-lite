"""
FraudLocate Lite - Unit Test Suite.
Validates all analytical, geospatial, and heuristic algorithms:
- Haversine distance calculation
- Travel time estimation
- Synthetic data generation
- Schema validation & cleaning pipeline
- DBSCAN clustering with Haversine metric
- Cluster statistics computation
- Patrol Coverage Priority ranking
- Nearest-Neighbor patrol route heuristic
"""

import math
import pytest
import pandas as pd
import numpy as np

from src.distance import (
    haversine_distance_km,
    haversine_distance_matrix,
    calculate_travel_time,
    EARTH_RADIUS_KM,
)
from utils.data_generator import generate_synthetic_dataset
from src.preprocessing import validate_and_preprocess
from src.clustering import run_dbscan_clustering
from src.hotspot_analysis import compute_cluster_statistics, rank_hotspots
from src.route_optimizer import build_nearest_neighbor_patrol_route


class TestDistanceCalculations:
    """Test spherical geodesic Haversine distance computations."""

    def test_haversine_known_points(self):
        # Hyderabad Charminar (17.3616, 78.4747) to Secunderabad Station (17.4399, 78.5018)
        # Expected real-world distance is ~9.1 to 9.3 km
        dist = haversine_distance_km(17.3616, 78.4747, 17.4399, 78.5018)
        assert 8.8 <= dist <= 9.6, f"Distance {dist} km out of expected range"

    def test_haversine_zero_distance(self):
        dist = haversine_distance_km(17.3850, 78.4867, 17.3850, 78.4867)
        assert dist == 0.0

    def test_haversine_matrix(self):
        pts = [(17.3850, 78.4867), (17.4399, 78.5018), (17.4486, 78.3908)]
        mat = haversine_distance_matrix(pts)
        assert mat.shape == (3, 3)
        assert mat[0, 0] == 0.0
        assert mat[1, 1] == 0.0
        assert mat[0, 1] == mat[1, 0]
        assert mat[0, 1] > 0.0

    def test_travel_time_calculation(self):
        # 30 km at 30 km/h = 1 hour = 60 mins
        result = calculate_travel_time(30.0, speed_kmh=30.0)
        assert result["time_hours"] == 1.0
        assert result["time_minutes"] == 60.0
        assert "disclaimer" in result


class TestDataGenerationAndCleaning:
    """Test synthetic data generator and preprocessing pipeline."""

    def test_generate_synthetic_dataset(self):
        df = generate_synthetic_dataset(num_records=200, city="Hyderabad")
        assert len(df) == 200
        assert "transaction_id" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns
        assert "withdrawal_amount" in df.columns
        assert "simulated_tag" in df.columns

    def test_preprocessing_valid_records(self):
        raw_df = generate_synthetic_dataset(num_records=150, city="Hyderabad")
        clean_df, summary = validate_and_preprocess(raw_df)

        assert len(clean_df) == 150
        assert summary["valid_records"] == 150
        assert summary["invalid_records"] == 0
        assert "hour" in clean_df.columns
        assert "day_of_week" in clean_df.columns
        assert "lat_rad" in clean_df.columns
        assert "lon_rad" in clean_df.columns

    def test_preprocessing_filters_invalid_data(self):
        bad_records = pd.DataFrame([
            {
                "transaction_id": "TXN_BAD_1",
                "timestamp": "2026-09-01 10:00:00",
                "latitude": 999.0,  # Invalid lat
                "longitude": 78.4,
                "atm_id": "ATM_1",
                "atm_name": "ATM 1",
                "area": "Zone",
                "city": "Hyderabad",
                "withdrawal_amount": 10000,
            },
            {
                "transaction_id": "TXN_BAD_2",
                "timestamp": "invalid_date_format",  # Invalid timestamp
                "latitude": 17.4,
                "longitude": 78.4,
                "atm_id": "ATM_2",
                "atm_name": "ATM 2",
                "area": "Zone",
                "city": "Hyderabad",
                "withdrawal_amount": 10000,
            },
            {
                "transaction_id": "TXN_BAD_3",
                "timestamp": "2026-09-01 12:00:00",
                "latitude": 17.4,
                "longitude": 78.4,
                "atm_id": "ATM_3",
                "atm_name": "ATM 3",
                "area": "Zone",
                "city": "Hyderabad",
                "withdrawal_amount": -500,  # Negative amount
            },
            {
                "transaction_id": "TXN_GOOD_1",
                "timestamp": "2026-09-01 14:00:00",
                "latitude": 17.4375,
                "longitude": 78.4482,
                "atm_id": "ATM_4",
                "atm_name": "ATM 4",
                "area": "Ameerpet",
                "city": "Hyderabad",
                "withdrawal_amount": 25000,
            },
        ])

        clean_df, summary = validate_and_preprocess(bad_records)
        assert len(clean_df) == 1
        assert clean_df.iloc[0]["transaction_id"] == "TXN_GOOD_1"
        assert summary["invalid_records"] == 3


class TestDBSCANAndHotspotRanking:
    """Test density-based spatial clustering and coverage priority ranking."""

    def test_dbscan_clustering_identifies_clusters(self):
        raw_df = generate_synthetic_dataset(num_records=500, city="Hyderabad", noise_ratio=0.10)
        clean_df, _ = validate_and_preprocess(raw_df)

        df_clustered, summary = run_dbscan_clustering(clean_df, radius_km=1.0, min_samples=5)

        assert "cluster_id" in df_clustered.columns
        assert summary["num_clusters"] >= 2, "Expected at least 2 clusters from synthetic data"
        assert summary["num_noise"] > 0, "Expected some noise points"
        assert -1 in df_clustered["cluster_id"].values

    def test_cluster_statistics_and_ranking(self):
        raw_df = generate_synthetic_dataset(num_records=500, city="Hyderabad")
        clean_df, _ = validate_and_preprocess(raw_df)
        df_clustered, summary = run_dbscan_clustering(clean_df, radius_km=1.0, min_samples=5)

        stats_df = compute_cluster_statistics(
            df_clustered,
            cluster_centroids=summary["cluster_centroids"],
            cluster_radii_km=summary["cluster_radii_km"]
        )

        assert not stats_df.empty
        assert "num_withdrawals" in stats_df.columns
        assert "total_withdrawal_amount" in stats_df.columns

        ranked_df = rank_hotspots(stats_df)
        assert "priority_score" in ranked_df.columns
        assert "priority_tier" in ranked_df.columns
        # Ensure highest score is ranked first
        assert ranked_df.iloc[0]["priority_score"] >= ranked_df.iloc[-1]["priority_score"]


class TestPatrolRouteSuggester:
    """Test Nearest-Neighbor patrol route generator."""

    def test_nearest_neighbor_route_generation(self):
        raw_df = generate_synthetic_dataset(num_records=500, city="Hyderabad")
        clean_df, _ = validate_and_preprocess(raw_df)
        df_clustered, summary = run_dbscan_clustering(clean_df, radius_km=1.0, min_samples=5)
        stats_df = compute_cluster_statistics(
            df_clustered,
            cluster_centroids=summary["cluster_centroids"],
            cluster_radii_km=summary["cluster_radii_km"]
        )
        ranked_df = rank_hotspots(stats_df)

        route = build_nearest_neighbor_patrol_route(
            ranked_df,
            speed_kmh=30.0,
            return_to_start=True,
            top_n=3
        )

        assert len(route["stops"]) == 5  # Start base + 3 stops + return base
        assert route["total_distance_km"] > 0.0
        assert route["estimated_travel_time"]["time_minutes"] > 0.0
        assert len(route["waypoints_coords"]) == 5
        assert not route["summary_table"].empty
