"""Automated unit and integration test suite for Regression Model Evaluation (025).

Verifies chronological fold ordering (>= 5 folds, max(train_idx) < min(val_idx), zero overlap,
zero shuffling, hold-out test isolation), per-fold causal feature and StandardScaler isolation,
mean +/- std MAE and RMSE aggregation, learning curve plotting, and technical/business reports.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from data.pipelines.sales_forecast import (
    DataLeakageError,
    TemporalCVFold,
    aggregate_fold_metric,
    build_causal_feature_matrix,
    calculate_mae,
    calculate_rmse,
    classify_model_fit,
    compute_learning_curve,
    create_temporal_cv_splits,
    create_temporal_partition,
    evaluate_temporal_cv,
    export_cv_metrics_json,
    fit_and_transform_features,
    generate_business_metric_doc,
    generate_evaluation_report,
    load_and_validate_sales_data,
    render_learning_curve,
    validate_fold_integrity,
)


@pytest.fixture
def sales_data_path() -> Path:
    """Return path to the canonical TrackFlow sales CSV."""
    return Path("data/raw/trackflow_sales.csv")


@pytest.fixture
def consolidated_df(sales_data_path: Path) -> pd.DataFrame:
    """Load the 120-month consolidated TrackFlow sales DataFrame."""
    return load_and_validate_sales_data(sales_data_path, market="consolidated")


# ==============================================================================
# T018: Chronological Fold Ordering, Count >= 5, Monotonicity & Leakage Rejection
# ==============================================================================


def test_temporal_cv_fold_count_and_monotonic_ordering(consolidated_df: pd.DataFrame) -> None:
    """T018: Verify >= 5 folds, strictly consecutive monotonic indices, max(train_idx) < min(val_idx), zero overlap, and hold-out isolation."""
    folds = create_temporal_cv_splits(consolidated_df, n_splits=5, train_months=96)

    # 1. At least 5 chronological folds produced
    assert len(folds) >= 5
    assert len(folds) == 5

    expected_train_sizes = [16, 32, 48, 64, 80]
    for i, fold in enumerate(folds):
        assert fold.fold_index == i + 1
        assert fold.train_size == expected_train_sizes[i]
        assert fold.val_size == 16
        assert len(fold.train_indices) == fold.train_size
        assert len(fold.val_indices) == fold.val_size

        # 2. Strictly consecutive monotonic increasing indices (zero shuffling)
        assert list(fold.train_indices) == sorted(fold.train_indices)
        assert list(fold.val_indices) == sorted(fold.val_indices)
        assert all(
            fold.train_indices[j + 1] - fold.train_indices[j] == 1
            for j in range(len(fold.train_indices) - 1)
        )
        assert all(
            fold.val_indices[j + 1] - fold.val_indices[j] == 1
            for j in range(len(fold.val_indices) - 1)
        )

        # 3. Strict chronological precedence: max(train_indices) < min(val_indices)
        assert max(fold.train_indices) < min(fold.val_indices)
        assert max(fold.train_indices) + 1 == min(fold.val_indices)
        assert fold.train_end < fold.val_start

        # 4. Zero overlap between train and validation sets
        assert set(fold.train_indices).isdisjoint(set(fold.val_indices))

        # 5. Hold-out 24-month test set (2024-01-01 to 2025-12-01, indices >= 96) is untouched
        assert max(fold.train_indices) < 96
        assert max(fold.val_indices) < 96
        assert fold.val_end <= datetime.date(2023, 12, 1)

        # 6. Consecutive folds advance strictly forward in time
        if i > 0:
            prev_fold = folds[i - 1]
            assert fold.train_end > prev_fold.train_end
            assert fold.val_start > prev_fold.val_start
            assert fold.val_end > prev_fold.val_end


def test_temporal_cv_rejects_shuffled_or_insufficient_splits(consolidated_df: pd.DataFrame) -> None:
    """T018: Verify DataLeakageError is raised when < 5 splits are requested or timestamps/indices are shuffled or overlapping."""
    # 1. Fewer than 5 splits must raise DataLeakageError
    with pytest.raises(DataLeakageError, match="n_splits >= 5"):
        create_temporal_cv_splits(consolidated_df, n_splits=4)

    # 2. Shuffled input DataFrame timestamps must raise DataLeakageError
    shuffled_df = consolidated_df.copy()
    row_10 = shuffled_df.iloc[10].copy()
    row_25 = shuffled_df.iloc[25].copy()
    shuffled_df.iloc[10] = row_25
    shuffled_df.iloc[25] = row_10
    with pytest.raises(DataLeakageError, match="Chronological ordering violation"):
        create_temporal_cv_splits(shuffled_df, n_splits=5)

    # 3. Validate fold integrity helper catches reversed/overlapping fold indices
    valid_folds = create_temporal_cv_splits(consolidated_df, n_splits=5)
    corrupted_fold = TemporalCVFold(
        fold_index=1,
        train_indices=(0, 1, 2, 20),  # Non-consecutive and overlaps val
        val_indices=(16, 17, 18, 19),
        train_start=datetime.date(2016, 1, 1),
        train_end=datetime.date(2017, 4, 1),
        val_start=datetime.date(2017, 5, 1),
        val_end=datetime.date(2018, 8, 1),
        train_size=4,
        val_size=4,
    )
    with pytest.raises(DataLeakageError):
        validate_fold_integrity([corrupted_fold, *valid_folds[1:]], min_splits=5)


# ==============================================================================
# T019: Per-Fold Feature Engineering & StandardScaler Isolation Verification
# ==============================================================================


def test_per_fold_scaler_and_feature_isolation(consolidated_df: pd.DataFrame) -> None:
    """T019: Verify that mutating future fold or hold-out revenue values does not alter earlier fold features, scaler parameters, or fold metrics."""
    baseline_summary = evaluate_temporal_cv(consolidated_df, n_splits=5, random_seed=42)

    # Mutate future revenue values in Fold 4/5 validation window (index >= 64) and hold-out test set (index >= 96)
    tampered_df = consolidated_df.copy()
    tampered_df.loc[64:, "revenue_eur"] = tampered_df.loc[64:, "revenue_eur"] * 50.0

    tampered_summary = evaluate_temporal_cv(tampered_df, n_splits=5, random_seed=42)

    # Folds 1, 2, and 3 only observe indices [0..31], [0..47], and [0..63] respectively!
    # Therefore their Training and Validation MAE/RMSE MUST be 100% identical to baseline.
    for fold_idx in range(3):
        orig_fold = baseline_summary.folds[fold_idx]
        tamp_fold = tampered_summary.folds[fold_idx]
        assert orig_fold.train_mae_eur == tamp_fold.train_mae_eur
        assert orig_fold.val_mae_eur == tamp_fold.val_mae_eur
        assert orig_fold.train_rmse_eur == tamp_fold.train_rmse_eur
        assert orig_fold.val_rmse_eur == tamp_fold.val_rmse_eur

    # Verify explicitly that within Fold 1 (train [0..15], val [16..31]), StandardScaler is fitted only on [0..15]
    partition = create_temporal_partition(consolidated_df, train_months=96, test_months=24)
    folds = create_temporal_cv_splits(partition.train_df, n_splits=5)
    fold_1 = folds[0]
    visible_slice = partition.train_df.iloc[: fold_1.val_indices[-1] + 1].copy().reset_index(drop=True)
    X_vis, _ = build_causal_feature_matrix(visible_slice)
    X_f1_train = X_vis.iloc[list(fold_1.train_indices)]
    X_f1_val = X_vis.iloc[list(fold_1.val_indices)]

    scaler, _, _ = fit_and_transform_features(X_f1_train, X_f1_val)
    np.testing.assert_allclose(scaler.mean_, X_f1_train.mean(axis=0).values, rtol=1e-6)
    np.testing.assert_allclose(scaler.scale_, X_f1_train.std(axis=0, ddof=0).values, rtol=1e-6)


# ==============================================================================
# T020: MAE & RMSE Mean ± Std Aggregation, Learning Curve & Reports Verification
# ==============================================================================


def test_mae_and_rmse_mean_std_aggregation(consolidated_df: pd.DataFrame) -> None:
    """T020: Verify calculate_mae, calculate_rmse, and 5-fold mean ± std (ddof=1) calculations."""
    y_true = np.array([100.0, 200.0, 300.0, 400.0])
    y_pred = np.array([110.0, 190.0, 330.0, 370.0])
    # Abs errors: [10, 10, 30, 30] -> MAE = 20.0
    # Sq errors: [100, 100, 900, 900] -> MSE = 500 -> RMSE = sqrt(500) = 22.36
    assert calculate_mae(y_true, y_pred) == 20.0
    assert calculate_rmse(y_true, y_pred) == 22.36

    summary = evaluate_temporal_cv(consolidated_df, n_splits=5, random_seed=42)
    assert summary.n_splits == 5
    assert len(summary.folds) == 5

    val_rmses = [f.val_rmse_eur for f in summary.folds]
    val_maes = [f.val_mae_eur for f in summary.folds]
    train_rmses = [f.train_rmse_eur for f in summary.folds]
    train_maes = [f.train_mae_eur for f in summary.folds]

    assert summary.val_rmse_mean_eur == round(float(np.mean(val_rmses)), 2)
    assert summary.val_rmse_std_eur == round(float(np.std(val_rmses, ddof=1)), 2)
    assert summary.val_mae_mean_eur == round(float(np.mean(val_maes)), 2)
    assert summary.val_mae_std_eur == round(float(np.std(val_maes, ddof=1)), 2)
    assert summary.train_rmse_mean_eur == round(float(np.mean(train_rmses)), 2)
    assert summary.train_rmse_std_eur == round(float(np.std(train_rmses, ddof=1)), 2)
    assert summary.train_mae_mean_eur == round(float(np.mean(train_maes)), 2)
    assert summary.train_mae_std_eur == round(float(np.std(train_maes, ddof=1)), 2)

    assert "±" in summary.formatted_train_mae
    assert "±" in summary.formatted_val_mae
    assert "±" in summary.formatted_train_rmse
    assert "±" in summary.formatted_val_rmse


def test_learning_curve_and_reports_generation(
    consolidated_df: pd.DataFrame,
    sales_data_path: Path,
    tmp_path: Path,
) -> None:
    """T020: Verify learning curve PNG, technical evaluation report, business metric doc, and JSON schema compliance."""
    from scripts.evaluate_sales_forecast import parse_args, run_evaluation

    eval_dir = tmp_path / "eval"
    docs_path = tmp_path / "docs" / "model-eval.md"

    args = parse_args(
        [
            "--data-path",
            str(sales_data_path),
            "--n-splits",
            "5",
            "--random-seed",
            "42",
            "--eval-dir",
            str(eval_dir),
            "--docs-path",
            str(docs_path),
        ]
    )
    exit_code = run_evaluation(args)
    assert exit_code == 0

    lc_png = eval_dir / "learning_curve.png"
    eval_md = eval_dir / "evaluation_report.md"
    cv_json = eval_dir / "cv_metrics.json"

    # 1. Learning curve image exists and is non-empty
    assert lc_png.exists()
    assert lc_png.stat().st_size > 10_000

    # 2. Technical evaluation report contains fit classification, mean ± std, root cause, corrective action, and staging decision
    assert eval_md.exists()
    eval_text = eval_md.read_text(encoding="utf-8")
    assert "overfitting" in eval_text
    assert "±" in eval_text
    assert "HOLD_REQUIRES_REMEDIATION" in eval_text
    assert "max_depth" in eval_text

    # 3. Business metric doc covers MAE, RMSE, Ana, Carlos, Thomas, Los Angeles (60%), Zaragoza (40%)
    assert docs_path.exists()
    docs_text = docs_path.read_text(encoding="utf-8")
    for keyword in (
        "MAE",
        "RMSE",
        "Ana",
        "Carlos",
        "Thomas",
        "Los Angeles",
        "Zaragoza",
        "revenue_eur",
        "shipments_processed",
        "±",
    ):
        assert keyword in docs_text, f"Expected '{keyword}' in docs/model-eval.md"

    # 4. CV metrics JSON conforms to evaluation-report-schema.json structure
    assert cv_json.exists()
    payload = json.loads(cv_json.read_text(encoding="utf-8"))
    assert payload["model_type"] == "random_forest"
    assert payload["random_seed"] == 42
    assert payload["n_splits"] == 5
    assert payload["train_partition_months"] == 96
    assert len(payload["folds"]) == 5
    assert payload["diagnosis"]["fit_classification"] in ("well-fitted", "underfitting", "overfitting")
    assert payload["diagnosis"]["primary_metric"] == "RMSE"
    assert "±" in payload["summary_metrics"]["formatted_val_rmse"]

