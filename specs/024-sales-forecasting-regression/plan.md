# Implementation Plan: Sales Forecasting With a Regression Model

**Branch**: `024-sales-forecasting-regression` | **Date**: 2026-11-10 | **Spec**: [spec.md](file:///J:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/024-sales-forecasting-regression/spec.md)

**Input**: Feature specification from `specs/024-sales-forecasting-regression/spec.md`

---

## Summary

Deliver a time-series sales forecasting pipeline and evaluation suite for TrackFlow's executive leadership (CEO Thomas, Operations Leads Ana and Carlos). The pipeline ingests 10 years (120 months, 2016–2025) of consolidated monthly sales from `data/raw/trackflow_sales.csv`, strictly partitioning the series into 8 years of training (96 months) and 2 years of out-of-sample testing (24 months) with zero lookahead leakage. A Random Forest regression model (backed by benchmark analysis vs. XGBoost) learns causal calendar, seasonal, and autoregressive lag dynamics, producing point forecasts and a 95% uncertainty/variability envelope. Performance is evaluated across four dimensions—MSE (in EUR² and % of average monthly revenue), Population Stability Index (PSI), Gini rank discrimination coefficient, and K2 residual normality test—generating visual and structured executive reports alongside an algorithm decision rationale in Spanish (`docs/training-model-decission.md`).

---

## Technical Context

**Language/Version**: Python 3.14+ (managed via `uv`)  
**Primary Dependencies**: `scikit-learn` (RandomForestRegressor, StandardScaler), `scipy` (stats, normaltest), `pandas` (time-series rolling & lagging), `numpy`, `matplotlib` (forecast visualization with uncertainty bands), `pytest`  
**Storage**: Flat CSV input (`data/raw/trackflow_sales.csv`), output JSON metrics (`reports/sales_forecast_evaluation.json`), output forecast chart (`reports/sales_forecast_test_eval.png`), decision markdown (`docs/training-model-decission.md`)  
**Testing**: `pytest` (`tests/pipelines/test_sales_forecast.py`)  
**Target Platform**: Cross-platform Python execution (Windows / Linux) orchestrated via `uv run`  
**Project Type**: Data Pipeline / Machine Learning CLI Script & Evaluation Engine  
**Performance Goals**: Deterministic pipeline execution in < 5 seconds; 100% reproducible with fixed seed (`random_state=42`)  
**Constraints**: Zero lookahead data leakage; strict temporal partition (96 train / 24 test); feature scalers fitted strictly on training data; no global `pip` modifications (`uv` exclusive)  
**Scale/Scope**: 120 continuous monthly observations (10 years) covering US, Spain, and consolidated operations  

---

## Constitution Check

*GATE: Evaluated before Phase 0 research and re-evaluated post Phase 1 design.*

| Principle / Gate | Status | Analysis & Compliance Justification |
|---|---|---|
| **I. Service Boundaries & Domain Isolation** | **PASS** | ML pipeline logic resides in `data/pipelines/sales_forecast/`, operational CLI runner resides in `scripts/train_sales_forecast.py`, input dataset in `data/raw/`, and tests in `tests/pipelines/`. No forbidden cross-boundary dependencies or frontend leaks. |
| **II. Public API Compatibility & Serialization** | **PASS (N/A)** | Does not modify public HTTP REST API routes in `services/api/`. Generates standalone file artifacts and CLI outputs adhering to JSON Schema. |
| **III. Strict TypeScript & Static Type Safety** | **PASS (N/A)** | Python modules enforce strict PEP 484 type annotations, explicit function return types, and complete docstrings. |
| **IV. Defensive Error Handling & Zero Data Leaks** | **PASS** | Ingestion pipeline checks data integrity (existence, non-empty, strictly positive revenue, continuous monthly sequence) and raises descriptive domain errors with clean exit codes. Zero PII or credentials present in sales data. |
| **V. Performance-First & Core Web Vitals** | **PASS (N/A)** | Standalone data/ML pipeline with no frontend bundle impact. |
| **VI. Test-First & Deterministic Verification Gates** | **PASS** | Automated unit tests in `tests/pipelines/test_sales_forecast.py` validate partition boundaries, 0% leakage, and metric mathematical properties with deterministic seed. |

*Pre-design Gate Status: ALL PASS. Post-design Gate Status: ALL PASS.*

---

## Project Structure

### Documentation & Specifications (this feature)

```text
specs/024-sales-forecasting-regression/
├── plan.md                                # This implementation plan
├── research.md                            # Phase 0: Algorithm choice, formulas, leakage prevention
├── data-model.md                          # Phase 1: Entities, schemas, feature matrices, data flow
├── quickstart.md                          # Phase 1: Runnable verification steps and expected outputs
└── contracts/                             # Phase 1: Interface contracts & schema
    ├── cli-contract.md                    # CLI interface specification for training script
    └── evaluation-summary-schema.json     # JSON schema for evaluation summary artifact
```

### Source Code & Deliverables Layout

```text
data/
├── pipelines/
│   └── sales_forecast/
│       ├── __init__.py                    # Module exports
│       ├── dataset.py                     # Ingestion, validation, and 8y/2y temporal partition
│       ├── features.py                    # Causal feature engineering (lags, rolling stats, calendar)
│       ├── model.py                       # Random Forest training and tree ensemble variance
│       ├── metrics.py                     # MSE, PSI, Gini coefficient, and K2 normality test
│       └── visualizer.py                  # Test evaluation chart with uncertainty band
└── raw/
    └── trackflow_sales.csv                # 120-month historical sales dataset (2016-2025)

docs/
├── sales-forecasting/
│   ├── trackflow-BRIEFING.en.md           # Business requirements & KPI definitions
│   └── trackflow-BRIEFING.es.md
└── training-model-decission.md            # Spanish algorithm justification (Random Forest vs XGBoost)

reports/
├── sales_forecast_test_eval.png           # Visual forecast chart with 95% uncertainty envelope
└── sales_forecast_evaluation.json         # Executive multi-metric JSON report

scripts/
└── train_sales_forecast.py                # Runnable CLI pipeline orchestrator

tests/
└── pipelines/
    └── test_sales_forecast.py             # Unit tests for partition integrity & feature causality
```

**Structure Decision**: Modularized pipeline package under `data/pipelines/sales_forecast/` adhering to existing pipeline patterns (`data/pipelines/pipeline.py`), with CLI entry point in `scripts/train_sales_forecast.py` and dedicated unit tests in `tests/pipelines/`.

---

## Complexity Tracking

> *No Constitution violations identified. No architecture exceptions required.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | N/A | N/A |
