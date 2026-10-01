"""
FraudLocate Lite - Data Loader Module.
Handles loading, caching, fallback generation, and export of synthetic withdrawal datasets.
"""

import os
from typing import Optional, Union, Tuple
import pandas as pd
from utils.data_generator import save_synthetic_dataset, SYNTHETIC_DATA_BANNER

DEFAULT_DATA_PATH = "data/synthetic_withdrawals.csv"


def load_withdrawal_dataset(
    file_source: Optional[Union[str, pd.DataFrame, object]] = None,
    auto_generate_if_missing: bool = True,
    default_records: int = 2500,
    city: str = "Hyderabad",
) -> pd.DataFrame:
    """
    Load withdrawal dataset from a file path, file-like buffer, or generate automatically.

    Args:
        file_source: Optional file path or uploaded file buffer.
        auto_generate_if_missing: If True and default CSV does not exist, generates it.
        default_records: Number of records to generate if creating fresh dataset.
        city: Default city name for synthetic generator.

    Returns:
        pd.DataFrame containing the raw dataset.
    """
    # 1. User provided an existing DataFrame
    if isinstance(file_source, pd.DataFrame):
        return file_source.copy()

    # 2. User uploaded a file-like buffer (e.g., Streamlit UploadedFile)
    if file_source is not None and hasattr(file_source, "read"):
        try:
            df = pd.read_csv(file_source)
            return df
        except Exception as e:
            raise ValueError(f"Failed to parse uploaded CSV: {e}")

    # 3. Path string provided
    path = file_source if (isinstance(file_source, str) and file_source) else DEFAULT_DATA_PATH

    if os.path.exists(path):
        return pd.read_csv(path)

    # 4. Fallback: Auto-generate synthetic dataset if missing
    if auto_generate_if_missing:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        save_synthetic_dataset(output_path=path, num_records=default_records, city=city)
        return pd.read_csv(path)

    raise FileNotFoundError(f"Dataset file not found at: {path}")


def convert_df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Encode DataFrame to UTF-8 CSV bytes for download button."""
    return df.to_csv(index=False).encode("utf-8")
