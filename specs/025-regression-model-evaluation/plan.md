# Implementation Plan: Regression Model Evaluation

**Branch**: `025-regression-model-evaluation` | **Date**: 2026-11-12 | **Spec**: [spec.md](file:///J:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/025-regression-model-evaluation/spec.md)

**Input**: Feature specification from `/specs/025-regression-model-evaluation/spec.md`

---

## Summary

Deliver a rigorous, leak-free multi-fold temporal cross-validation and model fit diagnostic suite for TrackFlow's consolidated monthly sales forecasting model (`RandomForestRegressor`, `n_estimators=100`, `random_state=42`). Operating strictly within the 8-year training partition (96 months: `2016-01-01` to `2023-12-01`) while keeping the 2-year hold-out test set (24 months: `2024-01-01` to `2025-12-01`) untouched, the evaluation pipeline splits the training history into 5 expanding chronological folds (`train_size` = 16, 32, 48, 64, 80 months; `val_size` = 16 months each). Within every fold, causal lag/rolling features and `StandardScaler` parameters are computed strictly from historical data available up to that fold's split boundary. The pipeline calculates Training and Validation **MAE** and **RMSE** across all folds, reporting results as `mean ± standard deviation`, renders a high-resolution learning curve (`data/eval/learning_curve.png`), generates a domain-grounded business cost comparison of MAE vs. RMSE (`docs/model-eval.md`) tailored to stakeholders Thomas (CEO), Ana (Warehouse), and Carlos (Carriers), produces a formal technical fit diagnosis (`well-fitted`, `underfitting`, or `overfitting`) with a root-cause corrective action and staging promotion verdict (`data/eval/evaluation_report.md`), and enforces chronological fold integrity via automated unit tests in `tests/pipelines/`.

---

## Technical Context

**Language/Version**: Python 3.14+ (managed exclusively via `uv`)  
**Primary Dependencies**: `scikit-learn` (`RandomForestRegressor`, `StandardScaler`, `TimeSeriesSplit`), `scipy`, `pandas`, `numpy`, `matplotlib` (non-interactive `Agg` backend for `learning_curve.png`), `pytest`  
**Storage**: Flat CSV input (`data/raw/trackflow_sales.csv`), output learning curve image (`data/eval/learning_curve.png`), technical evaluation report (`data/eval/evaluation_report.md`), structured CV metrics JSON (`data/eval/cv_metrics.json`), business metric justification (`docs/model-eval.md`)  
**Testing**: `pytest` (`tests/pipelines/test_regression_evaluation.py` and `tests/pipelines/test_sales_forecast.py`)  
**Target Platform**: Cross-platform Python CLI execution (Windows / Linux) via `uv run --project services/api`  
**Project Type**: Machine Learning Evaluation Pipeline, Diagnostic Visualizer & Technical Reporting CLI  
**Performance Goals**: Complete 5-fold expanding temporal cross-validation, learning curve plotting, and markdown/JSON report generation in < 5 seconds; 100% deterministic with `random_state=42`  
**Constraints**: Zero lookahead leakage across folds; strict chronological fold ordering (`max(train_indices) < min(val_indices)`); at least 5 temporal folds; all metrics reported as `mean ± std`; package management strictly via `uv` (`FR-010`)  
**Scale/Scope**: 120 consolidated monthly observations (`2016-01` to `2025-12`), evaluating 5 expanding folds across the 96-month training partition (`2016-01` to `2023-12`)  

---

## Constitution Check

*GATE: Evaluated before Phase 0 research and re-evaluated after Phase 1 design.*

| Principle / Gate | Status | Analysis & Compliance Justification |
|---|---|---|
| **I. Service Boundaries & Domain Isolation** | **PASS** | All evaluation logic resides in `data/pipelines/sales_forecast/`, the CLI orchestrator resides in `scripts/evaluate_sales_forecast.py`, evaluation artifacts are written to `data/eval/` and `docs/model-eval.md`, and tests reside in `tests/pipelines/`. Zero coupling with `uis/` or `services/api/` database files. |
| **II. Public API Compatibility & Serialization** | **PASS (N/A)** | Does not modify any FastAPI HTTP routes in `services/api/`. CLI and JSON outputs adhere to explicit contracts (`contracts/cli-contract.md` and `contracts/evaluation-report-schema.json`). |
| **III. Strict TypeScript & Static Type Safety** | **PASS** | Python modules enforce strict PEP 484 type annotations, frozen/typed dataclasses, `Literal` union types for fit classifications, and comprehensive docstrings. TypeScript packages remain untouched and pass `npm run typecheck`. |
| **IV. Defensive Error Handling & Zero Data Leaks** | **PASS** | Explicit domain exceptions (`DatasetValidationError`, `DataLeakageError`) guard against missing files, unsorted timestamps, `< 5` folds, or overlapping fold indices, exiting with deterministic non-zero codes (`1`, `2`, `3`). Zero PII or credentials exist in aggregated sales data. |
| **V. Performance-First & Core Web Vitals** | **PASS (N/A)** | Offline ML evaluation pipeline and static markdown/PNG artifacts with zero impact on Next.js frontend bundles. |
| **VI. Test-First & Deterministic Verification Gates** | **PASS** | Dedicated `pytest` suite (`tests/pipelines/test_regression_evaluation.py`) deterministically verifies chronological fold ordering, zero feature/scaler leakage, `mean ± std` metric math, and artifact generation. |

*Pre-design Gate Status: ALL PASS. Post-design Gate Status: ALL PASS.*

---

## Project Structure

### Documentation (this feature)

```text
specs/025-regression-model-evaluation/
├── plan.md                                # This implementation plan (/speckit-plan output)
├── research.md                            # Phase 0 output: CV strategy, MAE vs RMSE, fit diagnosis
├── data-model.md                          # Phase 1 output: Entities, schemas, validation rules, flow
├── quickstart.md                          # Phase 1 output: Runnable verification commands & checks
├── contracts/                             # Phase 1 output: CLI & JSON schema contracts
│   ├── cli-contract.md                    # CLI interface specification for evaluate_sales_forecast.py
│   └── evaluation-report-schema.json      # JSON schema for data/eval/cv_metrics.json
└── tasks.md                               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code & Deliverables (repository root)

```text
data/
├── eval/
│   ├── learning_curve.png                 # Generated learning curve plot (Train vs Val MAE & RMSE)
│   ├── evaluation_report.md               # Formal technical fit diagnosis & staging recommendation
│   └── cv_metrics.json                    # Structured 5-fold cross-validation metrics (mean ± std)
├── pipelines/
│   └── sales_forecast/
│       ├── __init__.py                    # Updated module exports
│       ├── dataset.py                     # Existing ingestion & 8y/2y temporal partition
│       ├── features.py                    # Existing causal feature matrix & train-isolated scaler
│       ├── model.py                       # Existing RandomForestRegressor training & uncertainty
│       ├── metrics.py                     # Extended with MAE calculation & fold metric helpers
│       ├── visualizer.py                  # Extended with render_learning_curve()
│       └── evaluator.py                   # NEW: 5-fold temporal CV splitter, leak-free fold runner, fit classifier, report writers
└── raw/
    └── trackflow_sales.csv                # Existing 120-month consolidated sales dataset

docs/
├── model-eval.md                          # NEW: Business cost justification of MAE vs. RMSE for TrackFlow
└── sales-forecasting/
    ├── trackflow-BRIEFING.en.md
    └── trackflow-BRIEFING.es.md

scripts/
├── train_sales_forecast.py                # Existing 024 training CLI script (preserved intact)
└── evaluate_sales_forecast.py             # NEW: CLI orchestrator for 5-fold CV, learning curve & reports

tests/
└── pipelines/
    ├── test_sales_forecast.py             # Existing 024 pipeline tests (preserved intact)
    └── test_regression_evaluation.py      # NEW: Chronological fold ordering, leakage & evaluation tests
```

**Structure Decision**: Extend the modular `data/pipelines/sales_forecast/` package introduced in `024-sales-forecasting-regression` with a dedicated `evaluator.py` module and `scripts/evaluate_sales_forecast.py` CLI entry point, writing evaluation deliverables to `data/eval/` and `docs/model-eval.md` and unit tests to `tests/pipelines/test_regression_evaluation.py` as required by `spec.md`.

---

## Complexity Tracking

> *No Constitution violations identified. No architectural exceptions required.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | N/A | N/A |
