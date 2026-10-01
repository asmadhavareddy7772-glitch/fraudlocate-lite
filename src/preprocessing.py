"""
FraudLocate Lite - Preprocessing & Data Validation Pipeline.
Validates synthetic ATM transaction records, cleans geospatial coordinates,
extracts temporal features, and computes data-quality metrics.
"""

from typing import Tuple, Dict, Any, List
import pandas as pd
import numpy as np

REQUIRED_COLUMNS = [
    "transaction_id",
    "timestamp",
    "latitude",
    "longitude",
    "atm_id",
    "atm_name",
    "area",
    "city",
    "withdrawal_amount",
]


def validate_and_preprocess(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Execute full validation and cleaning pipeline on withdrawal records.

    Pipeline Steps:
    1. Check presence of required schema columns.
    2. Coerce numeric fields and coordinates.
    3. Filter out invalid, out-of-bound, or NaN coordinates.
    4. Parse datetime timestamps and extract temporal features (date, time, hour, day_of_week).
    5. Deduplicate transactions by transaction_id.
    6. Ensure withdrawal amounts are positive numeric values.
    7. Compute radians for geospatial clustering.
    8. Compile detailed data quality summary report.

    Args:
        df: Raw DataFrame loaded from CSV or user upload.

    Returns:
        (clean_df, data_quality_summary)
    """
    total_raw = len(df)
    if total_raw == 0:
        empty_summary = {
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "unique_atms": 0,
            "unique_areas": 0,
            "date_range": "N/A",
            "total_withdrawal_amount": 0,
            "avg_withdrawal_amount": 0.0,
            "data_quality_pct": 0.0,
            "issues": ["The uploaded or provided dataset is completely empty."],
        }
        return df, empty_summary

    issues: List[str] = []

    # 1. Validate required columns
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Dataset is missing required columns: {', '.join(missing_cols)}. "
            f"Required columns are: {', '.join(REQUIRED_COLUMNS)}"
        )

    clean_df = df.copy()

    # 2. Coerce coordinates and amounts to numeric
    clean_df["latitude"] = pd.to_numeric(clean_df["latitude"], errors="coerce")
    clean_df["longitude"] = pd.to_numeric(clean_df["longitude"], errors="coerce")
    clean_df["withdrawal_amount"] = pd.to_numeric(clean_df["withdrawal_amount"], errors="coerce")

    # 3. Filter valid coordinates (Earth limits: lat in [-90, 90], lon in [-180, 180])
    coord_valid = (
        clean_df["latitude"].notna()
        & clean_df["longitude"].notna()
        & clean_df["latitude"].between(-90.0, 90.0)
        & clean_df["longitude"].between(-180.0, 180.0)
    )
    dropped_coords = total_raw - int(coord_valid.sum())
    if dropped_coords > 0:
        issues.append(f"Dropped {dropped_coords} records with invalid/missing latitude or longitude.")
    clean_df = clean_df[coord_valid].copy()

    # 4. Parse timestamp
    clean_df["parsed_timestamp"] = pd.to_datetime(clean_df["timestamp"], format="mixed", errors="coerce")
    valid_ts = clean_df["parsed_timestamp"].notna()
    dropped_ts = len(clean_df) - int(valid_ts.sum())
    if dropped_ts > 0:
        issues.append(f"Dropped {dropped_ts} records with unparseable timestamps.")
    clean_df = clean_df[valid_ts].copy()

    # 5. Extract temporal features
    clean_df["date"] = clean_df["parsed_timestamp"].dt.strftime("%Y-%m-%d")
    clean_df["time"] = clean_df["parsed_timestamp"].dt.strftime("%H:%M:%S")
    clean_df["hour"] = clean_df["parsed_timestamp"].dt.hour
    clean_df["day_of_week"] = clean_df["parsed_timestamp"].dt.day_name()
    clean_df["day_number"] = clean_df["parsed_timestamp"].dt.dayofweek  # 0=Monday, 6=Sunday

    # 6. Filter valid positive withdrawal amount
    amount_valid = clean_df["withdrawal_amount"].notna() & (clean_df["withdrawal_amount"] > 0)
    dropped_amounts = len(clean_df) - int(amount_valid.sum())
    if dropped_amounts > 0:
        issues.append(f"Dropped {dropped_amounts} records with invalid/non-positive withdrawal amounts.")
    clean_df = clean_df[amount_valid].copy()

    # 7. Deduplicate transaction_id
    initial_len = len(clean_df)
    clean_df = clean_df.drop_duplicates(subset=["transaction_id"], keep="first")
    dropped_dupes = initial_len - len(clean_df)
    if dropped_dupes > 0:
        issues.append(f"Removed {dropped_dupes} duplicate transaction IDs.")

    # 8. Handle missing strings
    clean_df["area"] = clean_df["area"].fillna("Unspecified Area").astype(str)
    clean_df["atm_id"] = clean_df["atm_id"].fillna("UNKNOWN_ATM").astype(str)
    clean_df["atm_name"] = clean_df["atm_name"].fillna("ATM Kiosk").astype(str)
    clean_df["city"] = clean_df["city"].fillna("Default City").astype(str)
    if "bank_branch" in clean_df.columns:
        clean_df["bank_branch"] = clean_df["bank_branch"].fillna("Main Branch").astype(str)
    else:
        clean_df["bank_branch"] = "Main Branch"

    # 9. Compute radians for Haversine calculations
    clean_df["lat_rad"] = np.radians(clean_df["latitude"])
    clean_df["lon_rad"] = np.radians(clean_df["longitude"])

    # 10. Summary report
    valid_count = len(clean_df)
    invalid_count = total_raw - valid_count
    quality_pct = round((valid_count / total_raw * 100.0), 2) if total_raw > 0 else 0.0

    if valid_count > 0:
        min_date = clean_df["date"].min()
        max_date = clean_df["date"].max()
        date_range_str = f"{min_date} to {max_date}"
        total_amount = float(clean_df["withdrawal_amount"].sum())
        avg_amount = float(clean_df["withdrawal_amount"].mean())
        unique_atms = int(clean_df["atm_id"].nunique())
        unique_areas = int(clean_df["area"].nunique())
    else:
        date_range_str = "None"
        total_amount = 0.0
        avg_amount = 0.0
        unique_atms = 0
        unique_areas = 0

    summary: Dict[str, Any] = {
        "total_records": total_raw,
        "valid_records": valid_count,
        "invalid_records": invalid_count,
        "data_quality_pct": quality_pct,
        "unique_atms": unique_atms,
        "unique_areas": unique_areas,
        "date_range": date_range_str,
        "total_withdrawal_amount": total_amount,
        "avg_withdrawal_amount": round(avg_amount, 2),
        "issues": issues,
    }

    # Clean temporary column and sort chronologically
    clean_df = clean_df.sort_values("parsed_timestamp").reset_index(drop=True)
    clean_df = clean_df.drop(columns=["parsed_timestamp"])

    return clean_df, summary
