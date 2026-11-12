# CLI Interface Contract: Regression Model Evaluation Pipeline

**Feature Branch**: `025-regression-model-evaluation`  
**Command**: `python scripts/evaluate_sales_forecast.py`

---

## 1. Synopsis

```bash
uv run --project services/api python scripts/evaluate_sales_forecast.py [OPTIONS]
```

Or via npm convenience script from the monorepo root:
```bash
npm run evaluate:sales-forecast
```

---

## 2. Arguments & Options

| Option Flag | Type | Default | Required | Description |
|---|---|---|---|---|
| `--data-path` | `Path` | `data/raw/trackflow_sales.csv` | No | Path to the raw TrackFlow sales CSV dataset |
| `--n-splits` | `int` | `5` | No | Number of chronological expanding cross-validation folds (`>= 5`) |
| `--random-seed` | `int` | `42` | No | Random seed for deterministic Random Forest execution |
| `--eval-dir` | `Path` | `data/eval` | No | Output directory for `learning_curve.png`, `evaluation_report.md`, and `cv_metrics.json` |
| `--docs-path` | `Path` | `docs/model-eval.md` | No | Output path for the business cost metric justification document |

---

## 3. Exit Codes

| Exit Code | Meaning | Circumstances |
|---|---|---|
| `0` | Success | Dataset validated, 5-fold chronological CV executed without leakage, learning curve saved, and markdown evaluation reports generated. |
| `1` | Dataset Validation Failure | Missing CSV file, corrupted columns, non-positive revenue, or discontinuous monthly sequence. |
| `2` | Temporal / Fold Leakage Error | Fewer than 5 folds requested, non-monotonic indices, overlapping train/val indices, or lookahead violation. |
| `3` | Runtime / Environment Error | Missing dependencies or unexpected I/O failure. |

---

## 4. Standard Output & Generated Artifacts

### Standard Output (stdout)
Prints a structured executive summary of the 5-fold temporal cross-validation:
```text
======================================================================
 TRACKFLOW REGRESSION MODEL EVALUATION — 5-FOLD TEMPORAL CV SUMMARY
======================================================================
Dataset: data/raw/trackflow_sales.csv (Training Partition: 96 months, 2016-01-01 to 2023-12-01)
Hold-Out Test Partition: 24 months (2024-01-01 to 2025-12-01) [ISOLATED / UNTOUCHED]
Cross-Validation Strategy: Expanding Window (5 Chronological Folds, Zero Leakage)

Per-Fold Metrics (EUR):
  Fold 1 (Train: 16m, Val: 16m) | Train MAE: €... | Val MAE: €... | Train RMSE: €... | Val RMSE: €...
  Fold 2 (Train: 32m, Val: 16m) | Train MAE: €... | Val MAE: €... | Train RMSE: €... | Val RMSE: €...
  Fold 3 (Train: 48m, Val: 16m) | Train MAE: €... | Val MAE: €... | Train RMSE: €... | Val RMSE: €...
  Fold 4 (Train: 64m, Val: 16m) | Train MAE: €... | Val MAE: €... | Train RMSE: €... | Val RMSE: €...
  Fold 5 (Train: 80m, Val: 16m) | Train MAE: €... | Val MAE: €... | Train RMSE: €... | Val RMSE: €...

Cross-Validation Summary (mean ± std across 5 folds):
  - Training MAE    : €... ± €...
  - Validation MAE  : €... ± €...
  - Training RMSE   : €... ± €...
  - Validation RMSE : €... ± €...

Model Fit Diagnosis : overfitting (or well-fitted / underfitting)
Primary Metric      : RMSE (Root Mean Squared Error)
Staging Decision    : HOLD_REQUIRES_REMEDIATION (or CONDITIONAL_PROMOTION / PROMOTE_TO_STAGING)

Artifacts Generated:
  - Learning Curve Plot       : data/eval/learning_curve.png
  - Technical Eval Report     : data/eval/evaluation_report.md
  - Business Metric Doc       : docs/model-eval.md
  - Structured CV Metrics JSON: data/eval/cv_metrics.json
======================================================================
```

### Generated File Artifacts Contract
1. `data/eval/learning_curve.png`: High-resolution (300 DPI) chart plotting Training and Validation MAE/RMSE across chronological sample sizes ($N = 16, 32, 48, 64, 80$).
2. `data/eval/evaluation_report.md`: Technical report classifying model fit (`well-fitted`, `underfitting`, or `overfitting`), reporting `mean ± std` CV metrics, analyzing learning curve convergence, prescribing a concrete root-cause corrective action, and stating the staging promotion recommendation.
3. `docs/model-eval.md`: Business cost analysis comparing MAE and RMSE on training and validation partitions, detailing the operational cost of overestimating vs. underestimating revenue for Ana (Warehouse), Carlos (Carriers), and Thomas (CEO), and justifying the primary metric choice.
4. `data/eval/cv_metrics.json`: Machine-readable JSON payload conforming to `evaluation-report-schema.json`.

