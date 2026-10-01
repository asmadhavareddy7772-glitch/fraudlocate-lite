"""
FraudLocate Lite - Synthetic Cybercrime Withdrawal Dataset Generator.
Generates realistic, clustered ATM cash withdrawal records for simulated patrol planning.

IMPORTANT:
All generated data is strictly SYNTHETIC and SIMULATED.
Locations, ATM names, and withdrawal patterns are artificial and do NOT represent
actual criminal activity or real-world banking transactions.
"""

import os
import argparse
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

SYNTHETIC_DATA_BANNER = "SYNTHETIC / SIMULATED DATA — NOT REAL FINANCIAL DATA"

# Pre-defined realistic urban cluster templates for Hyderabad (Configurable)
HYDERABAD_CENTERS = [
    {
        "area": "Ameerpet Commercial Hub",
        "zone": "Central Zone",
        "center_lat": 17.4375,
        "center_lon": 78.4482,
        "std_dev_km": 0.35,
        "weight": 0.28,
        "activity_tier": "High",
        "peak_hours": [13, 14, 15, 18, 19, 20, 21],
        "atms": [
            ("ATM_HYD_101", "SBI Kiosk - Ameerpet Metro Junction", "State Bank of India"),
            ("ATM_HYD_102", "HDFC 24x7 Cash Point - Maitrivanam", "HDFC Bank"),
            ("ATM_HYD_103", "ICICI e-Lobby - Ameerpet Cross Roads", "ICICI Bank"),
            ("ATM_HYD_104", "Axis Bank ATM - Elephant House", "Axis Bank"),
            ("ATM_HYD_105", "Canara Bank Express ATM - SR Nagar", "Canara Bank"),
        ],
    },
    {
        "area": "Madhapur Tech Corridor",
        "zone": "Cyberabad Zone",
        "center_lat": 17.4486,
        "center_lon": 78.3908,
        "std_dev_km": 0.45,
        "weight": 0.24,
        "activity_tier": "High",
        "peak_hours": [17, 18, 19, 20, 21, 22, 23],
        "atms": [
            ("ATM_HYD_201", "Kotak ATM - Cyber Towers Concourse", "Kotak Mahindra"),
            ("ATM_HYD_202", "SBI ATM - Hitec City Metro Pillar 24", "State Bank of India"),
            ("ATM_HYD_203", "HDFC Bank E-Corner - Inorbit Road", "HDFC Bank"),
            ("ATM_HYD_204", "ICICI Bank Express ATM - Madhapur Police Station", "ICICI Bank"),
            ("ATM_HYD_205", "IndusInd Bank 24/7 ATM - Kavuri Hills", "IndusInd Bank"),
        ],
    },
    {
        "area": "Secunderabad Station Transit Hub",
        "zone": "North Zone",
        "center_lat": 17.4399,
        "center_lon": 78.5018,
        "std_dev_km": 0.40,
        "weight": 0.18,
        "activity_tier": "Medium",
        "peak_hours": [11, 12, 13, 14, 19, 20],
        "atms": [
            ("ATM_HYD_301", "Punjab National Bank - Railway Gate 1", "Punjab National Bank"),
            ("ATM_HYD_302", "Bank of Baroda ATM - Clock Tower Cir", "Bank of Baroda"),
            ("ATM_HYD_303", "SBI Multi-Service Lounge - Station Rd", "State Bank of India"),
            ("ATM_HYD_304", "Union Bank ATM - Patny Circle", "Union Bank of India"),
        ],
    },
    {
        "area": "Dilsukhnagar Market Corridor",
        "zone": "East Zone",
        "center_lat": 17.3688,
        "center_lon": 78.5247,
        "std_dev_km": 0.38,
        "weight": 0.12,
        "activity_tier": "Medium",
        "peak_hours": [14, 15, 16, 17, 20, 21],
        "atms": [
            ("ATM_HYD_401", "SBI Express ATM - Dilsukhnagar Metro", "State Bank of India"),
            ("ATM_HYD_402", "Andhra Bank (UBI) ATM - Chaitanyapuri", "Union Bank of India"),
            ("ATM_HYD_403", "HDFC Cash Machine - Malakpet Link", "HDFC Bank"),
            ("ATM_HYD_404", "Canara Bank ATM - Dilsukhnagar Bus Depot", "Canara Bank"),
        ],
    },
    {
        "area": "Charminar Heritage Bazaar",
        "zone": "South Zone",
        "center_lat": 17.3616,
        "center_lon": 78.4747,
        "std_dev_km": 0.30,
        "weight": 0.08,
        "activity_tier": "Low-Medium",
        "peak_hours": [15, 16, 17, 18, 19, 22],
        "atms": [
            ("ATM_HYD_501", "Bank of India - Madina Market", "Bank of India"),
            ("ATM_HYD_502", "SBI ATM - Gulzar Houz", "State Bank of India"),
            ("ATM_HYD_503", "HDFC Bank Kiosk - Nayapul Bridge", "HDFC Bank"),
        ],
    },
]

# Typical mule cash-out amounts (spikes often occur at ATM per-card/transaction limits)
TYPICAL_WITHDRAWAL_AMOUNTS = [
    10000, 15000, 20000, 25000, 30000, 40000, 50000
]
AMOUNT_WEIGHTS = [0.15, 0.10, 0.25, 0.20, 0.10, 0.10, 0.10]


def km_to_deg(km: float, lat: float) -> tuple[float, float]:
    """Convert offset in kilometers to degrees latitude and longitude at given latitude."""
    d_lat = km / 111.0
    d_lon = km / (111.0 * max(0.1, np.cos(np.radians(lat))))
    return d_lat, d_lon


def generate_synthetic_dataset(
    num_records: int = 2500,
    city: str = "Hyderabad",
    noise_ratio: float = 0.10,
    start_date: str = "2026-08-01",
    end_date: str = "2026-09-30",
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic withdrawal dataset with configured geographic clusters and noise.

    Args:
        num_records: Total number of records (default: 2500).
        city: City name (default: 'Hyderabad').
        noise_ratio: Fraction of records generated as uniform spatial noise (default: 0.10).
        start_date: ISO start date string.
        end_date: ISO end date string.
        random_seed: Random seed for reproducibility.

    Returns:
        DataFrame adhering to required schema with synthetic banner.
    """
    np.random.seed(random_seed)
    random.seed(random_seed)

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    total_seconds = int((end_dt - start_dt).total_seconds())

    num_noise = int(num_records * noise_ratio)
    num_clustered = num_records - num_noise

    # Normalize cluster weights
    cluster_weights = [c["weight"] for c in HYDERABAD_CENTERS]
    cluster_weights = np.array(cluster_weights) / sum(cluster_weights)

    # City bounding box for random noise (covering greater Hyderabad)
    min_lat, max_lat = 17.3000, 17.5200
    min_lon, max_lon = 78.3300, 78.5800

    records = []
    txn_counter = 1

    # 1. Generate clustered points
    cluster_indices = np.random.choice(len(HYDERABAD_CENTERS), size=num_clustered, p=cluster_weights)

    for c_idx in cluster_indices:
        cluster_info = HYDERABAD_CENTERS[c_idx]
        c_lat = cluster_info["center_lat"]
        c_lon = cluster_info["center_lon"]
        std_km = cluster_info["std_dev_km"]

        # Gaussian perturbation around cluster center
        lat_offset_km = np.random.normal(0, std_km)
        lon_offset_km = np.random.normal(0, std_km)
        d_lat, d_lon = km_to_deg(1.0, c_lat)
        point_lat = round(float(c_lat + lat_offset_km * d_lat), 6)
        point_lon = round(float(c_lon + lon_offset_km * d_lon), 6)

        # Select ATM from cluster's known kiosks or nearby branch
        atm_choice = random.choice(cluster_info["atms"])
        atm_id, atm_name, bank_name = atm_choice

        # Date & Time generation biased towards peak hours
        rand_offset_sec = random.randint(0, total_seconds)
        record_dt = start_dt + timedelta(seconds=rand_offset_sec)

        # 70% probability of falling into peak hour of the cluster
        if random.random() < 0.70:
            target_hour = random.choice(cluster_info["peak_hours"])
            record_dt = record_dt.replace(
                hour=target_hour,
                minute=random.randint(0, 59),
                second=random.randint(0, 59)
            )

        amount = int(np.random.choice(TYPICAL_WITHDRAWAL_AMOUNTS, p=AMOUNT_WEIGHTS))
        # Add slight occasional variation
        if random.random() < 0.15:
            amount += random.choice([-2000, 2000, 5000])
            amount = max(2000, min(50000, amount))

        branch_id = f"Branch_{random.randint(10, 49)}"

        records.append({
            "transaction_id": f"TXN{txn_counter:06d}",
            "timestamp": record_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "date": record_dt.strftime("%Y-%m-%d"),
            "time": record_dt.strftime("%H:%M:%S"),
            "day_of_week": record_dt.strftime("%A"),
            "hour": record_dt.hour,
            "latitude": point_lat,
            "longitude": point_lon,
            "atm_id": atm_id,
            "atm_name": atm_name,
            "area": cluster_info["area"],
            "city": city,
            "withdrawal_amount": amount,
            "bank_branch": branch_id,
            "transaction_type": "ATM_CASH_WITHDRAWAL",
            "simulated_tag": SYNTHETIC_DATA_BANNER,
        })
        txn_counter += 1

    # 2. Generate spatial noise (unclustered / sparse points)
    outlier_atms = [
        ("ATM_HYD_901", "Rural Kiosk - Outer Ring Road Exit 4", "Regional Rural Bank"),
        ("ATM_HYD_902", "Petrol Pump ATM - Medchal Highway", "Canara Bank"),
        ("ATM_HYD_903", "Market Yard Cash Point - Shamshabad Link", "State Bank of India"),
        ("ATM_HYD_904", "Express ATM - Uppal Outskirts", "Bank of India"),
        ("ATM_HYD_905", "Highway Kiosk - Patancheru Depot", "Punjab National Bank"),
    ]

    for _ in range(num_noise):
        noise_lat = round(float(np.random.uniform(min_lat, max_lat)), 6)
        noise_lon = round(float(np.random.uniform(min_lon, max_lon)), 6)

        rand_offset_sec = random.randint(0, total_seconds)
        record_dt = start_dt + timedelta(seconds=rand_offset_sec)

        atm_choice = random.choice(outlier_atms)
        atm_id, atm_name, bank_name = atm_choice

        amount = int(np.random.choice(TYPICAL_WITHDRAWAL_AMOUNTS, p=AMOUNT_WEIGHTS))
        branch_id = f"Branch_{random.randint(50, 99)}"

        records.append({
            "transaction_id": f"TXN{txn_counter:06d}",
            "timestamp": record_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "date": record_dt.strftime("%Y-%m-%d"),
            "time": record_dt.strftime("%H:%M:%S"),
            "day_of_week": record_dt.strftime("%A"),
            "hour": record_dt.hour,
            "latitude": noise_lat,
            "longitude": noise_lon,
            "atm_id": atm_id,
            "atm_name": atm_name,
            "area": "Isolated / Peripheral Zone",
            "city": city,
            "withdrawal_amount": amount,
            "bank_branch": branch_id,
            "transaction_type": "ATM_CASH_WITHDRAWAL",
            "simulated_tag": SYNTHETIC_DATA_BANNER,
        })
        txn_counter += 1

    df = pd.DataFrame(records)
    # Sort chronologically
    df["dt_temp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("dt_temp").drop(columns=["dt_temp"]).reset_index(drop=True)
    return df


def save_synthetic_dataset(
    output_path: str = "data/synthetic_withdrawals.csv",
    num_records: int = 2500,
    city: str = "Hyderabad",
) -> str:
    """Generate and save the synthetic dataset to CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df = generate_synthetic_dataset(num_records=num_records, city=city)
    df.to_csv(output_path, index=False)
    print(f"[{SYNTHETIC_DATA_BANNER}] Successfully generated {len(df)} records -> {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic ATM withdrawal dataset.")
    parser.add_argument("--records", type=int, default=2500, help="Number of records to generate")
    parser.add_argument("--city", type=str, default="Hyderabad", help="Synthetic city name")
    parser.add_argument("--output", type=str, default="data/synthetic_withdrawals.csv", help="Output CSV path")
    args = parser.parse_args()

    save_synthetic_dataset(output_path=args.output, num_records=args.records, city=args.city)
