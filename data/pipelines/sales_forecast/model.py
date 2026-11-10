"""Model training and uncertainty estimation module for TrackFlow sales forecasting.

Implements Random Forest regression with tree-ensemble prediction variance
and 95% uncertainty envelope quantification.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


@dataclass
class ForecastPredictionPoint:
    """Individual monthly forecast point with prediction intervals and tree variance.

    Attributes:
        month: Calendar month date string ('YYYY-MM-01') or date object.
        actual_revenue_eur: Ground-truth observed revenue in EUR (if available).
        predicted_revenue_eur: Point forecast from ensemble mean in EUR.
        lower_bound_eur: 95% lower prediction limit (mean - 1.96 * sigma) in EUR.
        upper_bound_eur: 95% upper prediction limit (mean + 1.96 * sigma) in EUR.
        residual_eur: Ground-truth residual error (actual - predicted) in EUR.
        tree_std_eur: Standard deviation across individual decision trees in EUR.
    """

    month: str
    actual_revenue_eur: float
    predicted_revenue_eur: float
    lower_bound_eur: float
    upper_bound_eur: float
    residual_eur: float
    tree_std_eur: float


def train_sales_forecaster(
    X_train: np.ndarray,
    y_train: np.ndarray | pd.Series,
    random_seed: int = 42,
    n_estimators: int = 100,
) -> RandomForestRegressor:
    """Train Random Forest regressor on historical training partition.

    Args:
        X_train: Feature matrix of training partition.
        y_train: Target revenue array of training partition.
        random_seed: Random seed for deterministic reproducibility (default: 42).
        n_estimators: Number of trees in the ensemble forest (default: 100).

    Returns:
        RandomForestRegressor: Fitted ensemble regression model.
    """
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=random_seed,
        n_jobs=-1,
    )
    y_values = np.asarray(y_train).ravel()
    model.fit(X_train, y_values)
    return model


def predict_with_uncertainty(
    model: RandomForestRegressor,
    X: np.ndarray,
    dates: Sequence[datetime.date | str],
    actual_y: Optional[np.ndarray | pd.Series] = None,
    train_mse: float = 0.0,
) -> List[ForecastPredictionPoint]:
    """Generate point predictions and 95% uncertainty envelopes across tree ensemble.

    Args:
        model: Fitted RandomForestRegressor instance.
        X: Feature matrix for evaluation or forecasting.
        dates: Sequence of calendar dates corresponding to rows in X.
        actual_y: Optional ground-truth revenue observations for calculating residuals.
        train_mse: In-sample training MSE added to tree variance for total variance.

    Returns:
        List[ForecastPredictionPoint]: Formatted prediction points with bounds.
    """
    # Extract predictions from each individual estimator tree
    # tree_preds shape: (n_estimators, n_samples)
    tree_preds = np.array([tree.predict(X) for tree in model.estimators_])

    # Ensemble mean point prediction
    mean_preds = np.mean(tree_preds, axis=0)

    # Prediction standard deviation across ensemble trees (sample std, ddof=1)
    tree_std = np.std(tree_preds, axis=0, ddof=1) if len(model.estimators_) > 1 else np.zeros_like(mean_preds)

    # Total standard error combining ensemble variance + training residual variance
    total_std = np.sqrt(np.square(tree_std) + max(0.0, train_mse))

    actuals = np.asarray(actual_y).ravel() if actual_y is not None else None

    results: List[ForecastPredictionPoint] = []
    for idx, d in enumerate(dates):
        date_str = d.strftime("%Y-%m-%d") if isinstance(d, (datetime.date, datetime.datetime)) else str(d)
        pred = float(mean_preds[idx])
        std = float(total_std[idx])
        act = float(actuals[idx]) if actuals is not None else 0.0
        resid = (act - pred) if actuals is not None else 0.0

        # 95% Confidence envelope: pred +/- 1.96 * total_std
        lower = max(0.0, pred - 1.96 * std)
        upper = pred + 1.96 * std

        results.append(
            ForecastPredictionPoint(
                month=date_str,
                actual_revenue_eur=round(act, 2),
                predicted_revenue_eur=round(pred, 2),
                lower_bound_eur=round(lower, 2),
                upper_bound_eur=round(upper, 2),
                residual_eur=round(resid, 2),
                tree_std_eur=round(float(tree_std[idx]), 2),
            )
        )

    return results

