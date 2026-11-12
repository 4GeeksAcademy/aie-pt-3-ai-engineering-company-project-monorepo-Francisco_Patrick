# Quickstart Validation Guide: Sales Forecasting With Regression Model

**Feature Branch**: `024-sales-forecasting-regression`  
**Date**: 2026-11-10  
**Status**: Completed  

---

## Prerequisites

- **Python Runtime**: Python 3.14+ (or compatible virtual environment).
- **Package Manager**: `uv` installed (`uv --version`).
- **Dependencies**: `scikit-learn`, `scipy`, `pandas`, `numpy`, `matplotlib`, `pytest`.
- **Dataset**: `data/raw/trackflow_sales.csv` must be present with 120 continuous monthly rows (2016-01-01 to 2025-12-01).

---

## 1. Environment Setup

Verify or sync Python dependencies using `uv`:

```bash
# Verify uv availability
uv --version

# Run script or tests directly via uv virtual environment (monorepo root)
uv run --project services/api python -c "import pandas, sklearn, scipy, matplotlib; print('All dependencies available')"
```

---

## 2. Automated Test Verification (Chronological Partition & Zero Leakage)

Execute the dedicated pipeline tests to verify temporal boundaries, partition sizing, and causal feature safety:

```bash
# Run isolated unit tests for the sales forecast pipeline (from monorepo root)
uv run --project services/api pytest tests/pipelines/test_sales_forecast.py -v

# Alternatively, using npm script:
npm run test:sales-forecast
```

### Expected Output:
- `test_sales_data_ingestion_and_schema`: **PASSED** (asserts 120 continuous rows, positive values).
- `test_temporal_split_sizes_and_boundaries`: **PASSED** (96 train rows, 24 test rows, zero overlap).
- `test_zero_lookahead_leakage_in_features`: **PASSED** (lags and rolling windows do not access future time steps).
- `test_feature_scaling_isolated_to_train`: **PASSED** (scaler parameters fitted exclusively on train set).
- `test_multi_metric_evaluation_integrity`: **PASSED** (MSE, PSI, Gini, and K2 calculated without NaN values).

---

## 3. Pipeline Execution (Training, Evaluation, and Visualization)

Run the end-to-end training and evaluation script:

```bash
# From monorepo root:
uv run --project services/api python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports

# Alternatively, using npm script:
npm run train:sales-forecast
```

### Expected Outcomes:
1. **Console Output**: Clean summary table printing:
   - Split verification (96 training months / 24 test months).
   - MSE in EUR² and percentage of average monthly revenue.
   - Population Stability Index (PSI) score.
   - Gini rank discrimination coefficient.
   - K2 score and residual normality p-value.
2. **Generated Artifacts**:
   - `reports/sales_forecast_test_eval.png`: High-resolution chart displaying actual revenue, predicted revenue, and 95% uncertainty/variability envelope for 2024–2025.
   - `reports/sales_forecast_evaluation.json`: Structured evaluation payload adhering to [evaluation-summary-schema.json](file:///J:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/024-sales-forecasting-regression/contracts/evaluation-summary-schema.json).
   - `docs/training-model-decission.md`: Architectural decision document in Spanish detailing the trade-off analysis between Random Forest and XGBoost.

---

## 4. Manual Artifact Inspection

Verify the generated visual forecast and documentation:

1. **Inspect Visualization**:
   - Check `reports/sales_forecast_test_eval.png`.
   - Confirm presence of November–December surges (25–35%) and February dips (10–15%).
   - Confirm that the shaded variability band wraps predicted points without temporal lag.
2. **Inspect Decision Document**:
   - Open `docs/training-model-decission.md`.
   - Verify Spanish text explaining:
     - Sample size trade-offs (120 observations).
     - Need for executive explainability (Thomas & Ana).
     - Hyperparameter tuning and overfitting resilience.

