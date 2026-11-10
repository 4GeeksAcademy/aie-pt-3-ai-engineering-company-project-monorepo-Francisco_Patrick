"""TrackFlow sales forecasting regression package.

Provides end-to-end time-series regression forecasting, zero-lookahead feature
engineering, multi-metric model evaluation, and visual reporting.
"""

from data.pipelines.sales_forecast.dataset import (
    DataLeakageError,
    DatasetValidationError,
    RawSalesRecord,
    TemporalPartition,
    create_temporal_partition,
    load_and_validate_sales_data,
)
from data.pipelines.sales_forecast.features import (
    FEATURE_COLUMNS,
    build_causal_feature_matrix,
    fit_and_transform_features,
)
from data.pipelines.sales_forecast.metrics import (
    ErrorMetricsResult,
    ModelEvaluationSummary,
    build_business_rationales,
    calculate_gini_coefficient,
    calculate_k2_normality,
    calculate_mse_and_nrmse,
    calculate_population_stability_index,
    export_evaluation_summary_json,
)
from data.pipelines.sales_forecast.model import (
    ForecastPredictionPoint,
    predict_with_uncertainty,
    train_sales_forecaster,
)
from data.pipelines.sales_forecast.visualizer import render_forecast_visualization

__all__ = [
    "DataLeakageError",
    "DatasetValidationError",
    "ErrorMetricsResult",
    "FEATURE_COLUMNS",
    "ForecastPredictionPoint",
    "ModelEvaluationSummary",
    "RawSalesRecord",
    "TemporalPartition",
    "build_business_rationales",
    "build_causal_feature_matrix",
    "calculate_gini_coefficient",
    "calculate_k2_normality",
    "calculate_mse_and_nrmse",
    "calculate_population_stability_index",
    "create_temporal_partition",
    "export_evaluation_summary_json",
    "fit_and_transform_features",
    "load_and_validate_sales_data",
    "predict_with_uncertainty",
    "render_forecast_visualization",
    "train_sales_forecaster",
]
