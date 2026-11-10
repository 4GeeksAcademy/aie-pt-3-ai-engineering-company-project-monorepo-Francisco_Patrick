# CLI Interface Contract: Sales Forecasting Pipeline

**Feature Branch**: `024-sales-forecasting-regression`  
**Command**: `python scripts/train_sales_forecast.py`

---

## 1. Synopsis

```bash
python scripts/train_sales_forecast.py [OPTIONS]
```

Or executed via `uv` from the monorepo root:
```bash
uv run --project services/api python scripts/train_sales_forecast.py [OPTIONS]
```

Or via npm convenience script:
```bash
npm run train:sales-forecast
```

*(Note: If the current working directory is already inside `services/api/`, `uv run python ../../scripts/train_sales_forecast.py [OPTIONS]` can also be run directly).*

---

## 2. Arguments & Options

| Option Flag | Type | Default | Required | Description |
|---|---|---|---|---|
| `--data-path` | `Path` | `data/raw/trackflow_sales.csv` | No | Path to the raw sales CSV dataset |
| `--model-type` | `Enum("random_forest", "xgboost")` | `random_forest` | No | Choice of regression algorithm |
| `--random-seed` | `int` | `42` | No | Random seed for deterministic execution |
| `--output-dir` | `Path` | `reports` | No | Directory to save evaluation artifacts |
| `--export-decision-doc` | `flag` | `True` | No | Auto-verifies/generates `docs/training-model-decission.md` |

---

## 3. Exit Codes

| Exit Code | Meaning | Circumstances |
|---|---|---|
| `0` | Success | Dataset validated, partition executed, model trained, metrics computed, and all artifacts generated. |
| `1` | Dataset Validation Failure | Missing CSV file, corrupted column headers, non-positive revenue, or missing dates in sequence. |
| `2` | Partition Leakage Error | Data split violates chronological ordering or contains row overlaps between train and test intervals. |
| `3` | Dependency / Environment Error | Missing required libraries or environment execution failure. |

---

## 4. Standard Output Streams

### Standard Output (stdout)
Outputs human-readable executive log:
```text
======================================================================
 TRACKFLOW SALES FORECASTING ENGINE — EXECUTIVE SUMMARY
======================================================================
Dataset: data/raw/trackflow_sales.csv (120 consolidated monthly records)
Temporal Split:
  - Training Period : 2016-01-01 to 2023-12-01 (96 months)
  - Test Period     : 2024-01-01 to 2025-12-01 (24 months)
  - Chronological Integrity: VERIFIED (Zero Leakage)

Model Architecture: Random Forest Regressor (n_estimators=100, seed=42)

Multi-Metric Evaluation on 24-Month Hold-Out Test Set:
  1. Mean Squared Error (MSE) : 1,482,912,400.00 EUR²
     - RMSE                   : 38,508.60 EUR
     - Error % of Mean Revenue: 2.85% (Average Revenue: 1,351,200.00 EUR)
  2. Population Stability (PSI): 0.042 (Status: STABLE)
  3. Gini Coefficient         : 0.785 (Strong seasonal separation)
  4. K2 Residual Normality    : Statistic=1.241, p-value=0.538 (Normality: ACCEPTED)

Artifacts Generated:
  - Visual Forecast Chart     : reports/sales_forecast_test_eval.png
  - Metric Summary JSON       : reports/sales_forecast_evaluation.json
  - Decision Document         : docs/training-model-decission.md
======================================================================
```

### Standard Error (stderr)
Reserved strictly for diagnostic errors and tracebacks upon non-zero exit codes.

