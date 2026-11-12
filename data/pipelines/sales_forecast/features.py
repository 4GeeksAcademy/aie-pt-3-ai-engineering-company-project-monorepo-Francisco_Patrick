"""Causal feature engineering and train-isolated feature scaling module.

Enforces strict zero-lookahead temporal integrity for time-series regression.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "month_num",
    "quarter",
    "is_peak_season",
    "is_february_dip",
    "trend_index",
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_12",
    "rolling_mean_3",
    "rolling_mean_6",
    "rolling_std_3",
]


def build_causal_feature_matrix(
    df: pd.DataFrame,
    base_year: int = 2016,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Construct causal feature matrix and target series with zero lookahead bias.

    All lag and rolling indicators use strictly past historical observations (shift >= 1).
    Early NaN values for lags before the 12th period are imputed forward from the initial
    historical observation to ensure no future information leaks into early periods.

    Args:
        df: Sales DataFrame containing 'month' and 'revenue_eur' columns.
        base_year: Benchmark starting year for secular trend indexing (default: 2016).

    Returns:
        Tuple[pd.DataFrame, pd.Series]:
            - X: DataFrame containing engineered features matching FEATURE_COLUMNS.
            - y: Series containing target revenue in EUR.
    """
    df_sorted = df.copy().reset_index(drop=True)
    month_dt = pd.to_datetime(df_sorted["month"])
    rev = df_sorted["revenue_eur"].astype(float)
    first_val = float(rev.iloc[0]) if len(rev) > 0 else 0.0

    features = pd.DataFrame(index=df_sorted.index)

    # 1. Calendar & Seasonal Indicators
    features["month_num"] = month_dt.dt.month.astype(int)
    features["quarter"] = month_dt.dt.quarter.astype(int)
    features["is_peak_season"] = month_dt.dt.month.isin([11, 12]).astype(int)
    features["is_february_dip"] = (month_dt.dt.month == 2).astype(int)

    # Secular trend index (months elapsed since Jan 2016)
    features["trend_index"] = (
        (month_dt.dt.year - base_year) * 12 + (month_dt.dt.month - 1)
    ).astype(int)

    # 2. Autoregressive Lag Features (strictly shift >= 1)
    features["lag_1"] = rev.shift(1).fillna(first_val)
    features["lag_2"] = rev.shift(2).fillna(first_val)
    features["lag_3"] = rev.shift(3).fillna(first_val)
    features["lag_12"] = rev.shift(12).fillna(first_val)

    # 3. Rolling Window Statistics (strictly shifted by 1 to prevent current-step leakage)
    shifted_rev = rev.shift(1).fillna(first_val)
    features["rolling_mean_3"] = shifted_rev.rolling(window=3, min_periods=1).mean()
    features["rolling_mean_6"] = shifted_rev.rolling(window=6, min_periods=1).mean()
    features["rolling_std_3"] = (
        shifted_rev.rolling(window=3, min_periods=1).std().fillna(0.0)
    )

    X = features[FEATURE_COLUMNS].copy()
    y = rev.copy()

    return X, y


def fit_and_transform_features(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
) -> Tuple[StandardScaler, np.ndarray, np.ndarray]:
    """Fit feature scaler strictly on the training partition and transform both partitions.

    Guarantees test statistics are never exposed during scaler parameter fitting.

    Args:
        X_train: Feature matrix for historical training partition.
        X_test: Feature matrix for unseen hold-out test partition.

    Returns:
        Tuple[StandardScaler, np.ndarray, np.ndarray]:
            - Fitted StandardScaler instance.
            - Scaled training feature array.
            - Scaled test feature array.
    """
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    return scaler, X_train_scaled, X_test_scaled

