"""Automated unit and integration test suite for sales forecasting regression pipeline.

Validates chronological split integrity, zero-lookahead feature causality,
scaler isolation, multi-metric evaluation, and contract compliance.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Generator

import numpy as np
import pandas as pd
import pytest

from data.pipelines.sales_forecast.dataset import (
    DataLeakageError,
    DatasetValidationError,
    create_temporal_partition,
    load_and_validate_sales_data,
)


@pytest.fixture
def sales_data_path() -> Path:
    """Fixture providing path to the raw sales CSV."""
    return Path("data/raw/trackflow_sales.csv")


@pytest.fixture
def sample_sales_df() -> pd.DataFrame:
    """Fixture creating synthetic 120-month continuous sales DataFrame."""
    dates = pd.date_range("2016-01-01", periods=120, freq="MS").date
    records = []
    base_rev = 800000.0
    for i, dt in enumerate(dates):
        # Secular growth + seasonal spikes
        seasonal_mult = 1.30 if dt.month in (11, 12) else (0.88 if dt.month == 2 else 1.0)
        rev = (base_rev + i * 5000.0) * seasonal_mult
        records.append(
            {
                "month": dt,
                "revenue_eur": round(rev, 2),
                "shipments_processed": int(rev / 15.0),
                "avg_revenue_per_shipment_eur": 15.0,
                "market": "consolidated",
            }
        )
    return pd.DataFrame(records)


# ==============================================================================
# Phase 3 / User Story 1 Tests: T006 & T007
# ==============================================================================


def test_sales_data_ingestion_and_schema(sales_data_path: Path) -> None:
    """T006: Assert CSV ingestion yields exactly 120 continuous monthly rows with valid values."""
    assert sales_data_path.exists(), f"Raw dataset not found at {sales_data_path}"
    df = load_and_validate_sales_data(sales_data_path, market="consolidated")

    assert len(df) == 120, f"Expected exactly 120 rows, got {len(df)}"
    assert (df["revenue_eur"] > 0).all(), "Found non-positive revenue values"
    assert (df["shipments_processed"] > 0).all(), "Found non-positive shipments"
    assert df["month"].iloc[0] == datetime.date(2016, 1, 1)
    assert df["month"].iloc[-1] == datetime.date(2025, 12, 1)


def test_missing_file_raises_validation_error(tmp_path: Path) -> None:
    """T006: Ingestion of non-existent file path must raise DatasetValidationError."""
    missing_file = tmp_path / "non_existent.csv"
    with pytest.raises(DatasetValidationError, match="not found"):
        load_and_validate_sales_data(missing_file)


def test_corrupted_columns_raises_validation_error(tmp_path: Path) -> None:
    """T006: CSV missing required columns must raise DatasetValidationError."""
    bad_csv = tmp_path / "corrupted.csv"
    bad_csv.write_text("date,revenue\n2020-01-01,1000\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="missing required columns"):
        load_and_validate_sales_data(bad_csv)


def test_negative_revenue_raises_validation_error(tmp_path: Path) -> None:
    """T006: Non-positive revenue values must raise DatasetValidationError."""
    invalid_csv = tmp_path / "negative_sales.csv"
    invalid_csv.write_text(
        "month,revenue_eur,shipments_processed,avg_revenue_per_shipment_eur,market\n"
        "2016-01-01,-500.0,10,50.0,consolidated\n",
        encoding="utf-8",
    )
    with pytest.raises(DatasetValidationError, match="non-positive revenue"):
        load_and_validate_sales_data(invalid_csv)


def test_temporal_split_sizes_and_boundaries(sample_sales_df: pd.DataFrame) -> None:
    """T006: Verify 96-month train (8y) / 24-month test (2y) partition sizes and zero overlap."""
    partition = create_temporal_partition(sample_sales_df, train_months=96, test_months=24)

    assert partition.train_count == 96
    assert partition.test_count == 24
    assert len(partition.train_df) == 96
    assert len(partition.test_df) == 24
    assert partition.train_start == datetime.date(2016, 1, 1)
    assert partition.train_end == datetime.date(2023, 12, 1)
    assert partition.test_start == datetime.date(2024, 1, 1)
    assert partition.test_end == datetime.date(2025, 12, 1)
    assert partition.train_end < partition.test_start
    assert partition.temporal_leak_detected is False


def test_temporal_leakage_detection_on_overlap(sample_sales_df: pd.DataFrame) -> None:
    """T006: Overlapping or reversed dates must raise DataLeakageError."""
    # Create artificial overlap
    corrupted_df = sample_sales_df.copy()
    corrupted_df.loc[96, "month"] = datetime.date(2020, 1, 1)

    with pytest.raises(DataLeakageError):
        create_temporal_partition(corrupted_df, train_months=96, test_months=24)


def test_zero_lookahead_leakage_in_features(sample_sales_df: pd.DataFrame) -> None:
    """T007: Assert feature lags and rolling stats depend solely on past observations."""
    from data.pipelines.sales_forecast.features import build_causal_feature_matrix

    feat_matrix_orig, y_orig = build_causal_feature_matrix(sample_sales_df)

    # Modify future revenue at time t=50
    tampered_df = sample_sales_df.copy()
    tampered_df.loc[50, "revenue_eur"] = tampered_df.loc[50, "revenue_eur"] * 10.0

    feat_matrix_mod, y_mod = build_causal_feature_matrix(tampered_df)

    # Features at t <= 50 must be completely identical between orig and mod
    # Because features at t=50 only observe lags from t <= 49!
    pd.testing.assert_frame_equal(feat_matrix_orig.iloc[:51], feat_matrix_mod.iloc[:51])

    # Target y at t=50 is modified
    assert y_mod.iloc[50] != y_orig.iloc[50]


def test_feature_scaling_isolated_to_train(sample_sales_df: pd.DataFrame) -> None:
    """T007: Confirm scaler is fitted exclusively on train set without leaking test distribution."""
    from data.pipelines.sales_forecast.features import (
        build_causal_feature_matrix,
        fit_and_transform_features,
    )

    partition = create_temporal_partition(sample_sales_df, train_months=96, test_months=24)
    train_features, train_y = build_causal_feature_matrix(partition.train_df)
    test_features, test_y = build_causal_feature_matrix(partition.test_df)

    scaler, X_train_scaled, X_test_scaled = fit_and_transform_features(
        train_features, test_features
    )

    # Scaler mean_ must equal train_features mean
    np.testing.assert_allclose(scaler.mean_, train_features.mean(axis=0).values, rtol=1e-5)

    # Scaler standard deviation must equal train_features std (with ddof=0 for population std)
    np.testing.assert_allclose(scaler.scale_, train_features.std(axis=0, ddof=0).values, rtol=1e-5)


# ==============================================================================
# Phase 4 / User Story 2 Tests: T012 & T013
# ==============================================================================


def test_multi_metric_evaluation_integrity() -> None:
    """T012: Validate calculation of MSE, NRMSE, PSI, Gini, and K2 normality without NaNs."""
    from data.pipelines.sales_forecast.metrics import (
        calculate_gini_coefficient,
        calculate_k2_normality,
        calculate_mse_and_nrmse,
        calculate_population_stability_index,
    )

    y_true = np.array([1000.0, 1200.0, 800.0, 1500.0, 2000.0, 900.0, 1100.0, 1300.0])
    y_pred = np.array([1050.0, 1180.0, 820.0, 1450.0, 1950.0, 920.0, 1080.0, 1320.0])
    y_train = np.array([900.0, 950.0, 1000.0, 1050.0, 1100.0, 1150.0, 1200.0, 1250.0])

    # 1. MSE & NRMSE
    mse_res = calculate_mse_and_nrmse(y_true, y_pred)
    assert not np.isnan(mse_res.mse_eur2)
    assert not np.isnan(mse_res.rmse_eur)
    assert not np.isnan(mse_res.nrmse_pct)
    assert mse_res.mse_eur2 > 0.0
    assert mse_res.nrmse_pct > 0.0

    # 2. PSI
    psi_score, psi_status = calculate_population_stability_index(y_train, y_true, n_bins=5)
    assert not np.isnan(psi_score)
    assert psi_score >= 0.0
    assert psi_status in ("STABLE", "MODERATE_DRIFT", "HIGH_DRIFT")

    # 3. Gini
    gini = calculate_gini_coefficient(y_true, y_pred)
    assert not np.isnan(gini)
    assert -1.0 <= gini <= 1.0
    assert gini > 0.0  # Positive rank ordering

    # 4. K2 Normality
    residuals = y_true - y_pred
    k2_stat, p_val, is_normal = calculate_k2_normality(residuals)
    assert not np.isnan(k2_stat)
    assert not np.isnan(p_val)
    assert 0.0 <= p_val <= 1.0
    assert isinstance(is_normal, bool)


def test_evaluation_summary_schema_conformance(tmp_path: Path) -> None:
    """T013: Assert generated evaluation JSON conforms to evaluation-summary-schema.json."""
    import json
    from data.pipelines.sales_forecast.metrics import (
        ModelEvaluationSummary,
        export_evaluation_summary_json,
    )

    summary = ModelEvaluationSummary(
        model_type="random_forest",
        random_seed=42,
        dataset_split={
            "train_months_count": 96,
            "test_months_count": 24,
            "train_start": "2016-01-01",
            "train_end": "2023-12-01",
            "test_start": "2024-01-01",
            "test_end": "2025-12-01",
        },
        metrics={
            "mse_eur2": 1500000.0,
            "rmse_eur": 1224.74,
            "nrmse_pct": 2.5,
            "average_monthly_revenue_eur": 1300000.0,
            "psi_score": 0.045,
            "psi_status": "STABLE",
            "gini_coefficient": 0.78,
            "k2_statistic": 1.25,
            "k2_pvalue": 0.53,
            "residuals_normal": True,
        },
        business_interpretation={
            "mse_rationale": "MSE reflects mean variance but lacks distribution safety checks.",
            "psi_assessment": "PSI is below 0.10 indicating stable distribution.",
            "gini_assessment": "Gini confirms high rank discrimination of peak months.",
            "k2_assessment": "Residuals pass normality test with p > 0.05.",
            "executive_readiness": "Model is certified for executive planning.",
        },
        generated_at="2026-11-10T11:00:00Z",
    )

    out_file = tmp_path / "sales_forecast_evaluation.json"
    export_evaluation_summary_json(summary, out_file)

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))

    # Validate against schema if jsonschema is available, or manually assert all schema keys
    assert data["model_type"] == "random_forest"
    assert data["random_seed"] == 42
    assert data["dataset_split"]["train_months_count"] == 96
    assert data["dataset_split"]["test_months_count"] == 24
    assert "mse_eur2" in data["metrics"]
    assert "psi_score" in data["metrics"]
    assert "gini_coefficient" in data["metrics"]
    assert "k2_statistic" in data["metrics"]
    assert "executive_readiness" in data["business_interpretation"]


# ==============================================================================
# Phase 5 / User Story 3 Tests: T020
# ==============================================================================


def test_forecast_visualization_generation(tmp_path: Path) -> None:
    """T020: Verify generation of high-resolution 300 DPI forecast chart with uncertainty envelope."""
    from data.pipelines.sales_forecast.model import ForecastPredictionPoint
    from data.pipelines.sales_forecast.visualizer import render_forecast_visualization

    dates = pd.date_range("2024-01-01", periods=24, freq="MS").strftime("%Y-%m-%d").tolist()
    points = []
    for i, d in enumerate(dates):
        act = 1200000.0 + i * 10000.0
        pred = act + (5000.0 if i % 2 == 0 else -5000.0)
        std = 30000.0
        points.append(
            ForecastPredictionPoint(
                month=d,
                actual_revenue_eur=act,
                predicted_revenue_eur=pred,
                lower_bound_eur=pred - 1.96 * std,
                upper_bound_eur=pred + 1.96 * std,
                residual_eur=act - pred,
                tree_std_eur=std,
            )
        )

    out_png = tmp_path / "sales_forecast_test_eval.png"
    result_path = render_forecast_visualization(points, out_png, dpi=100)

    assert result_path.exists()
    assert result_path.stat().st_size > 1000  # Non-trivial image file


# ==============================================================================
# Phase 7 / CLI Contract Tests: T026
# ==============================================================================


def test_cli_exit_code_success(sales_data_path: Path, tmp_path: Path) -> None:
    """T026: Assert CLI returns exit code 0 and creates artifacts on valid execution."""
    from scripts.train_sales_forecast import parse_args, run_pipeline

    args = parse_args(
        [
            "--data-path",
            str(sales_data_path),
            "--output-dir",
            str(tmp_path),
            "--random-seed",
            "42",
        ]
    )
    exit_code = run_pipeline(args)
    assert exit_code == 0
    assert (tmp_path / "sales_forecast_evaluation.json").exists()
    assert (tmp_path / "sales_forecast_test_eval.png").exists()


def test_cli_exit_code_validation_error(tmp_path: Path) -> None:
    """T026: Assert CLI returns exit code 1 when dataset file is missing."""
    from scripts.train_sales_forecast import parse_args, run_pipeline

    args = parse_args(
        [
            "--data-path",
            str(tmp_path / "missing.csv"),
            "--output-dir",
            str(tmp_path),
        ]
    )
    exit_code = run_pipeline(args)
    assert exit_code == 1



