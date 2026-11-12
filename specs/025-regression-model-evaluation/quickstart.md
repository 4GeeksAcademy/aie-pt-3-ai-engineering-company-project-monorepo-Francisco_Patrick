# Quickstart Validation Guide: Regression Model Evaluation

**Feature Branch**: `025-regression-model-evaluation`  
**Date**: 2026-11-12  
**Status**: Completed  

---

## Prerequisites

- **Python Runtime**: Python 3.12+ / 3.14+ managed via `uv`.
- **Package Manager**: `uv` exclusively (`FR-010`; never use `pip install` or `pipenv`).
- **Dependencies**: `scikit-learn`, `scipy`, `pandas`, `numpy`, `matplotlib`, `pytest` (pre-configured in `services/api/pyproject.toml`).
- **Input Dataset**: `data/raw/trackflow_sales.csv` (120 continuous `consolidated` monthly rows from `2016-01-01` to `2025-12-01`).

---

## 1. Environment Verification

From the monorepo root, confirm the `uv` virtual environment and required packages are available:

```bash
uv --version
uv run --project services/api python -c "import pandas, sklearn, scipy, matplotlib; print('Environment ready')"
```

---

## 2. Run Automated Chronological Fold Integrity & Evaluation Tests

Execute the automated test suite in `tests/pipelines/` to verify:
1. At least 5 chronological folds are produced on the 96-month training partition (`2016-01` to `2023-12`) while keeping the 24-month test partition (`2024-01` to `2025-12`) isolated.
2. Within every fold, `max(train_indices) < min(val_indices)`, indices are monotonically increasing with zero overlap or shuffling, and consecutive folds advance strictly forward in time.
3. Feature engineering and `StandardScaler` fitting are isolated per fold with zero future leakage.
4. Both MAE and RMSE are computed and formatted as `mean ± std` across all folds.

```bash
# Run all pipeline tests (including existing 024 tests and new 025 evaluation tests)
uv run --project services/api pytest tests/pipelines/ -v
```

### Expected Test Outcomes:
- `test_temporal_cv_fold_count_and_monotonic_ordering`: **PASSED** (verifies $\ge 5$ folds, strictly increasing indices, `max(train_idx) < min(val_idx)`, zero overlap).
- `test_temporal_cv_rejects_shuffled_or_insufficient_splits`: **PASSED** (verifies `DataLeakageError` is raised if fewer than 5 folds or out-of-order dates occur).
- `test_per_fold_scaler_and_feature_isolation`: **PASSED** (verifies future fold tampering does not alter earlier fold features or scaler parameters).
- `test_mae_and_rmse_mean_std_aggregation`: **PASSED** (verifies `mean ± std` calculations for Training and Validation MAE/RMSE).
- `test_learning_curve_and_reports_generation`: **PASSED** (verifies `data/eval/learning_curve.png`, `data/eval/evaluation_report.md`, and `docs/model-eval.md`).

---

## 3. Execute End-to-End Regression Model Evaluation

Run the evaluation CLI orchestrator to perform 5-fold temporal cross-validation, render the learning curve, and generate the technical and business evaluation documents:

```bash
uv run --project services/api python scripts/evaluate_sales_forecast.py \
  --data-path data/raw/trackflow_sales.csv \
  --n-splits 5 \
  --random-seed 42 \
  --eval-dir data/eval \
  --docs-path docs/model-eval.md
```

### Expected Artifacts & Validation Checks:
1. **Learning Curve Plot (`data/eval/learning_curve.png`)**:
   - Visually plots Training Error and Validation Error as a function of chronological training sample size ($16, 32, 48, 64, 80$ months).
2. **Technical Evaluation & Staging Report (`data/eval/evaluation_report.md`)**:
   - Explicitly classifies the model fit as `well-fitted`, `underfitting`, or `overfitting`.
   - Cites empirical `mean ± std` MAE and RMSE across the 5 temporal folds and learning curve convergence behavior.
   - Specifies a concrete, root-cause-aligned corrective action and staging promotion recommendation.
3. **Business Metric Justification (`docs/model-eval.md`)**:
   - Reports Training and Validation MAE and RMSE (`mean ± std`).
   - Analyzes the asymmetric operational costs of overestimating vs. underestimating monthly shipment revenue (`revenue_eur`, `shipments_processed`) for Ana (Warehouse), Carlos (Carriers across the 60/40 Los Angeles/Zaragoza hubs), and Thomas (CEO), and justifies the primary metric choice.
4. **Structured Metrics JSON (`data/eval/cv_metrics.json`)**:
   - Conforms to [evaluation-report-schema.json](file:///J:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/025-regression-model-evaluation/contracts/evaluation-report-schema.json).

