"""Dataset ingestion, validation, and temporal partitioning module.

Provides domain types, validation checks, and leak-free temporal splitting
for the TrackFlow sales forecasting regression pipeline.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd


class DatasetValidationError(Exception):
    """Raised when the sales dataset fails integrity, schema, or value validation."""


class DataLeakageError(Exception):
    """Raised when data partitioning violates temporal isolation or introduces lookahead leakage."""


@dataclass(frozen=True)
class RawSalesRecord:
    """Represents a validated single monthly sales record.

    Attributes:
        month: First day of the reporting month.
        revenue_eur: Consolidated monthly revenue in EUR (strictly > 0).
        shipments_processed: Count of shipments processed across all hubs (strictly > 0).
        avg_revenue_per_shipment_eur: Average revenue generated per shipment (strictly > 0).
        market: Regional segment identifier (e.g. 'consolidated', 'us', 'spain').
    """

    month: datetime.date
    revenue_eur: float
    shipments_processed: int
    avg_revenue_per_shipment_eur: float
    market: str


@dataclass
class TemporalPartition:
    """Container holding strictly isolated train and hold-out test partitions.

    Attributes:
        train_start: First calendar date in the training window.
        train_end: Last calendar date in the training window.
        test_start: First calendar date in the test window.
        test_end: Last calendar date in the test window.
        train_count: Exact number of training observations.
        test_count: Exact number of hold-out test observations.
        train_df: Training DataFrame containing historical observations.
        test_df: Hold-out test DataFrame containing unseen future observations.
        temporal_leak_detected: Flag asserting zero temporal overlap (must be False).
    """

    train_start: datetime.date
    train_end: datetime.date
    test_start: datetime.date
    test_end: datetime.date
    train_count: int
    test_count: int
    train_df: pd.DataFrame
    test_df: pd.DataFrame
    temporal_leak_detected: bool = False


REQUIRED_COLUMNS: Sequence[str] = (
    "month",
    "revenue_eur",
    "shipments_processed",
    "avg_revenue_per_shipment_eur",
    "market",
)


def load_and_validate_sales_data(
    data_path: str | Path,
    market: str = "consolidated",
) -> pd.DataFrame:
    """Load sales CSV dataset, validate integrity, and filter by market segment.

    Args:
        data_path: File system path to the input CSV file.
        market: Target market segment to isolate (defaults to 'consolidated').

    Returns:
        pd.DataFrame: Cleaned, sorted, and validated DataFrame indexed chronologically.

    Raises:
        DatasetValidationError: If the file does not exist, contains corrupted columns,
            non-positive revenue values, or missing monthly intervals in the sequence.
    """
    path = Path(data_path)
    if not path.is_file():
        raise DatasetValidationError(f"Sales dataset file not found at path: {path}")

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise DatasetValidationError(f"Failed to parse CSV file at {path}: {exc}") from exc

    # Validate column presence
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise DatasetValidationError(
            f"Dataset is missing required columns: {missing_cols}. Found: {list(df.columns)}"
        )

    # Filter target market
    market_df = df[df["market"].str.lower() == market.lower()].copy()
    if market_df.empty:
        raise DatasetValidationError(
            f"No records found for market '{market}'. Available markets: {df['market'].unique().tolist()}"
        )

    # Parse and sort by month
    try:
        market_df["month"] = pd.to_datetime(market_df["month"], format="%Y-%m-%d").dt.date
    except Exception as exc:
        raise DatasetValidationError(f"Error parsing date format in 'month' column: {exc}") from exc

    market_df = market_df.sort_values("month").reset_index(drop=True)

    # Validate strictly positive metrics
    if (market_df["revenue_eur"] <= 0).any():
        invalid_rows = market_df[market_df["revenue_eur"] <= 0]
        raise DatasetValidationError(
            f"Dataset contains {len(invalid_rows)} non-positive revenue records: {invalid_rows[['month', 'revenue_eur']]}"
        )

    if (market_df["shipments_processed"] <= 0).any():
        raise DatasetValidationError("Dataset contains non-positive shipments_processed records.")

    # Validate temporal continuity (expected consecutive monthly dates)
    months = pd.to_datetime(market_df["month"])
    expected_range = pd.date_range(start=months.min(), end=months.max(), freq="MS")
    if len(months) != len(expected_range):
        missing_months = expected_range.difference(months)
        raise DatasetValidationError(
            f"Discontinuous time series detected. Missing {len(missing_months)} monthly periods: "
            f"{[d.strftime('%Y-%m-%d') for d in missing_months]}"
        )

    return market_df


def create_temporal_partition(
    df: pd.DataFrame,
    train_months: int = 96,
    test_months: int = 24,
) -> TemporalPartition:
    """Chronologically split sales data into training and test partitions with zero lookahead leak.

    Args:
        df: Chronologically sorted sales DataFrame.
        train_months: Number of continuous historical months for training (default: 96, 8 years).
        test_months: Number of continuous out-of-sample months for testing (default: 24, 2 years).

    Returns:
        TemporalPartition: Isolated train and test slices with verified temporal integrity.

    Raises:
        DataLeakageError: If chronological boundaries overlap or total observations do not match
            the requested partition sizes.
    """
    total_expected = train_months + test_months
    if len(df) < total_expected:
        raise DataLeakageError(
            f"Insufficient records for partition: requires {total_expected} rows, but DataFrame has {len(df)}."
        )

    # Slice sequentially
    train_df = df.iloc[:train_months].copy().reset_index(drop=True)
    test_df = df.iloc[train_months : total_expected].copy().reset_index(drop=True)

    train_start = train_df["month"].min()
    train_end = train_df["month"].max()
    test_start = test_df["month"].min()
    test_end = test_df["month"].max()

    # Leakage check: Train end MUST strictly precede test start
    if train_end >= test_start:
        raise DataLeakageError(
            f"Temporal boundary violation: train_end ({train_end}) >= test_start ({test_start})."
        )

    # Overlap check
    train_dates = set(train_df["month"])
    test_dates = set(test_df["month"])
    overlap = train_dates.intersection(test_dates)
    if overlap:
        raise DataLeakageError(
            f"Data leakage detected! Overlapping timestamps found between train and test: {overlap}"
        )

    return TemporalPartition(
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
        train_count=len(train_df),
        test_count=len(test_df),
        train_df=train_df,
        test_df=test_df,
        temporal_leak_detected=False,
    )

