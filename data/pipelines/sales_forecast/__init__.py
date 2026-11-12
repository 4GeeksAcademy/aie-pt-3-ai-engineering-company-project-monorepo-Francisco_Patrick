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
from data.pipelines.sales_forecast.evaluator import (
    FoldMetricsRecord,
    LearningCurvePoint,
    ModelFitDiagnosis,
    TemporalCVFold,
    TemporalCVSummary,
    classify_model_fit,
    compute_learning_curve,
    create_temporal_cv_splits,
    evaluate_temporal_cv,
    export_cv_metrics_json,
    generate_business_metric_doc,
    generate_evaluation_report,
    validate_fold_integrity,
)
from data.pipelines.sales_forecast.features import (
    FEATURE_COLUMNS,
    build_causal_feature_matrix,
    fit_and_transform_features,
)
from data.pipelines.sales_forecast.metrics import (
    ErrorMetricsResult,
    ModelEvaluationSummary,
    aggregate_fold_metric,
    build_business_rationales,
    calculate_gini_coefficient,
    calculate_k2_normality,
    calculate_mae,
    calculate_mse_and_nrmse,
    calculate_population_stability_index,
    calculate_rmse,
    export_evaluation_summary_json,
)
from data.pipelines.sales_forecast.model import (
    ForecastPredictionPoint,
    predict_with_uncertainty,
    train_sales_forecaster,
)
from data.pipelines.sales_forecast.visualizer import (
    render_forecast_visualization,
    render_learning_curve,
)

__all__ = [
    "DataLeakageError",
    "DatasetValidationError",
    "ErrorMetricsResult",
    "FEATURE_COLUMNS",
    "FoldMetricsRecord",
    "ForecastPredictionPoint",
    "LearningCurvePoint",
    "ModelEvaluationSummary",
    "ModelFitDiagnosis",
    "RawSalesRecord",
    "TemporalCVFold",
    "TemporalCVSummary",
    "TemporalPartition",
    "aggregate_fold_metric",
    "build_business_rationales",
    "build_causal_feature_matrix",
    "calculate_gini_coefficient",
    "calculate_k2_normality",
    "calculate_mae",
    "calculate_mse_and_nrmse",
    "calculate_population_stability_index",
    "calculate_rmse",
    "classify_model_fit",
    "compute_learning_curve",
    "create_temporal_cv_splits",
    "create_temporal_partition",
    "evaluate_temporal_cv",
    "export_cv_metrics_json",
    "export_evaluation_summary_json",
    "fit_and_transform_features",
    "generate_business_metric_doc",
    "generate_evaluation_report",
    "load_and_validate_sales_data",
    "predict_with_uncertainty",
    "render_forecast_visualization",
    "render_learning_curve",
    "train_sales_forecaster",
    "validate_fold_integrity",
]
