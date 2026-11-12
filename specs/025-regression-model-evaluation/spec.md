# Feature Specification: Regression Model Evaluation

**Feature Branch**: `025-regression-model-evaluation`

**Created**: 2026-11-12

**Status**: Draft

**Input**: User description: "/speckit-specify # Feature: Regression Model Evaluation"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-Fold Temporal Cross-Validation Without Leakage (Priority: P1)

Executive leadership (CEO Thomas) and operational planners (Ana in Warehouse Operations and Carlos in Carrier Management) need empirical verification that the TrackFlow consolidated monthly revenue forecasting model (`revenue_eur` for `consolidated` market rows) performs consistently across multiple historical time horizons—not just on a single split—before promoting the model to the staging environment.

**Why this priority**: A model evaluated on a single static window can mask instability across alternating high-growth and low-growth years (3% to 9% annual growth variation). Multi-fold temporal validation across the 8-year training history (2016–2023) proves whether the model generalizes reliably across successive seasonal cycles without peeking into future data.

**Independent Test**: Can be independently tested by running the temporal cross-validation process across at least 5 chronological folds on the 96-month training dataset, verifying that every fold strictly preserves chronological order without shuffling, isolating causal lag/rolling features and scaling within each fold's historical boundary, and outputting validation metrics as `mean ± standard deviation`.

**Acceptance Scenarios**:

1. **Given** the 8-year (96-month, `2016-01` to `2023-12`) consolidated training dataset, **When** temporal cross-validation executes across at least 5 sequential folds, **Then** each fold's training indices strictly precede its validation indices in chronological order with zero shuffling or overlap.
2. **Given** causal time-series features (autoregressive lags, rolling window statistics, and calendar signals) and feature scaling, **When** each cross-validation fold is constructed and evaluated, **Then** feature transformations and scaling parameters are computed strictly within each fold's available historical window so no future fold information leaks backward.
3. **Given** completed evaluation across all temporal folds, **When** cross-validation performance is summarized, **Then** both MAE and RMSE are reported as `mean ± standard deviation` across the folds for both training and validation partitions rather than a single aggregated figure.

---

### User Story 2 - Learning Curve Generation & Model Fit Diagnosis (Priority: P2)

Engineering and finance decision-makers need a visual learning curve and a formal technical evaluation report (`data/eval/evaluation_report.md`) that diagnoses whether the revenue forecasting model is underfitting, overfitting, or well-fitted as training history grows, paired with a concrete, root-cause-driven corrective action and a staging promotion recommendation.

**Why this priority**: Before approving promotion to staging, stakeholders must verify whether errors stem from high bias (underfitting seasonal peaks in November–December or February dips) or high variance (memorizing historical training noise on a compact 96-month sample), and know the exact remediation required.

**Independent Test**: Can be independently tested by generating the learning curve chart in `data/eval/` showing training and validation error trajectories across increasing chronological training sizes, and inspecting `data/eval/evaluation_report.md` to confirm it contains an explicit fit classification (`well-fitted`, `underfitting`, or `overfitting`) backed by empirical fold metrics and a targeted corrective action.

**Acceptance Scenarios**:

1. **Given** the chronological training dataset, **When** the learning curve evaluation runs across progressively larger training subsets, **Then** a visual plot comparing training error and validation error against training sample size is saved to `data/eval/`.
2. **Given** the empirical cross-validation results (`mean ± standard deviation`) and learning curve trajectories, **When** `data/eval/evaluation_report.md` is generated, **Then** it explicitly classifies the model as `well-fitted`, `underfitting`, or `overfitting` and cites quantitative evidence from the training-to-validation error gap and fold stability.
3. **Given** the diagnosed model fit in `data/eval/evaluation_report.md`, **When** reviewing the staging readiness decision, **Then** the report specifies a concrete, domain-grounded corrective action directly addressing the root cause of the observed error pattern (avoiding generic unsubstantiated advice).

---

### User Story 3 - Business Cost Metric Justification: MAE vs. RMSE (Priority: P3)

Executive and operational stakeholders (Thomas, Ana, and Carlos) require a clear written analysis (`docs/model-eval.md`) comparing Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) across training and validation sets, justifying which metric best captures the actual financial and operational cost of overestimating versus underestimating TrackFlow's monthly shipment revenue.

**Why this priority**: TrackFlow bills by e-commerce shipment volume (`shipments_processed` and `avg_revenue_per_shipment_eur` across US/Los Angeles and Spain/Zaragoza hubs) and experiences sharp seasonal spikes (+25–35% in November–December for Black Friday/Christmas) and troughs (-10–15% in February). Stakeholders need a primary evaluation metric aligned with the asymmetric operational damage of missing peak capacity versus over-allocating warehouse and carrier resources.

**Independent Test**: Can be independently tested by verifying that both MAE and RMSE are computed for training and validation sets and that `docs/model-eval.md` documents the quantitative values and a domain-specific justification linking error direction (overestimation vs. underestimation) and error magnitude to TrackFlow's warehouse, carrier, and executive planning costs.

**Acceptance Scenarios**:

1. **Given** model predictions across the training and validation partitions, **When** error metrics are calculated, **Then** both MAE and RMSE (in `revenue_eur`) are accurately computed and recorded for both training and validation sets.
2. **Given** TrackFlow's operational context in `docs/sales-forecasting/trackflow-BRIEFING.es.md`, **When** reviewing `docs/model-eval.md`, **Then** the document explicitly compares the business impact of overestimating versus underestimating sales (warehouse staffing and packaging commitments for Ana, carrier capacity contracting for Carlos, and anomaly detection vs. normal seasonal dips for Thomas) and justifies the selection of the primary metric (MAE or RMSE).

---

### User Story 4 - Automated Chronological Fold Integrity Verification (Priority: P4)

Quality assurance and data engineering teams require an automated test suite in `tests/pipelines/` that continuously verifies that the temporal cross-validation splitter maintains strict chronological ordering and prevents any temporal overlap or feature leakage across folds.

**Why this priority**: Automated verification prevents accidental regressions (such as enabling random shuffling or global pre-split feature imputation) that would silently invalidate model evaluation gates prior to staging deployment.

**Independent Test**: Can be tested independently by executing the test suite in `tests/pipelines/` and verifying that tests pass when folds are strictly ordered and fail if any future timestamp or index precedes an earlier fold's boundary.

**Acceptance Scenarios**:

1. **Given** the temporal cross-validation splitting function, **When** the automated test in `tests/pipelines/` executes, **Then** it confirms at least 5 folds are produced, all indices within each fold are monotonically increasing, the maximum training index in every fold is strictly less than the minimum validation index of that fold, and validation windows advance chronologically across consecutive folds.

---

### Edge Cases

- **Boundary Leakage from Global Lag/Rolling Pre-computation**: If lag features (`lag_1`, `lag_2`, `lag_3`, `lag_12`) or rolling statistics (`rolling_mean_3`, `rolling_mean_6`, `rolling_std_3`) or standardization scalers are fitted across the entire dataset prior to fold splitting, validation folds will contain information derived from future observations or future distribution statistics. The evaluation pipeline must isolate feature scaling and boundary imputation strictly within each fold's visible window.
- **Small Early-Fold Sample Sizes in Expanding Windows**: In expanding-window temporal cross-validation on a 96-month training set with 5+ folds, the earliest fold contains a smaller number of months (e.g., 16 months), which spans only one full annual seasonal cycle (one November–December peak and one February dip). The learning curve and fold standard deviation analysis must account for higher variance in early folds when diagnosing model fit.
- **Missing or Out-of-Order Timestamps**: If input records from `data/raw/trackflow_sales.csv` are unsorted or missing expected monthly intervals (`2016-01-01` to `2025-12-01`), the evaluation pipeline must sort or reject the dataset before constructing temporal folds.
- **Zero-Variance or Degenerate Fold Predictions**: If a fold's validation window falls entirely outside peak season months (missing November–December), metrics must still compute deterministically without division-by-zero errors.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST confirm and preserve compatibility with the existing TrackFlow sales forecasting dataset (`data/raw/trackflow_sales.csv`, filtering `market == "consolidated"`, target `revenue_eur`), its causal time-series features (`month_num`, `quarter`, `is_peak_season`, `is_february_dip`, `trend_index`, `lag_1`, `lag_2`, `lag_3`, `lag_12`, `rolling_mean_3`, `rolling_mean_6`, `rolling_std_3`), and the 8-year training (96 months: `2016-01` to `2023-12`) / 2-year testing (24 months: `2024-01` to `2025-12`) temporal split.
- **FR-002**: System MUST implement a temporal cross-validation strategy using at least 5 chronological folds over the 8-year training partition without shuffling or mixing observations.
- **FR-003**: System MUST prevent data leakage across fold boundaries by ensuring causal lag/rolling feature imputation and feature scaling are computed strictly from historical data available up to each fold's split boundary, with zero lookahead into validation folds or the 2-year hold-out test set.
- **FR-004**: System MUST calculate both **MAE** (Mean Absolute Error) and **RMSE** (Root Mean Squared Error) in EUR (`revenue_eur`) across both training and validation sets for every cross-validation fold.
- **FR-005**: System MUST report cross-validation metrics as `mean ± standard deviation` across the folds for both training and validation partitions, rather than a single aggregated score.
- **FR-006**: System MUST generate a learning curve plotting training error and validation error as a function of chronological training sample size, and save the resulting visualization image in `data/eval/` (specifically `data/eval/learning_curve.png`).
- **FR-007**: System MUST provide a written metric selection and business cost justification in `docs/model-eval.md` that:
  - Reports the calculated training and validation MAE and RMSE values.
  - Analyzes the business cost asymmetry of overestimating versus underestimating monthly revenue (`revenue_eur`) and shipment volume (`shipments_processed`) for TrackFlow stakeholders—specifically Ana (warehouse staffing and packaging preparation), Carlos (carrier capacity commitments across the 60/40 Los Angeles and Zaragoza volume split), and Thomas (distinguishing normal February seasonal dips of -10–15% and November–December peaks of +25–35% from structural operational anomalies).
  - Justifies which metric (MAE or RMSE) serves as the primary decision metric for TrackFlow based on those domain error costs.
- **FR-008**: System MUST generate a formal technical diagnosis and evaluation report at `data/eval/evaluation_report.md` that:
  - Explicitly classifies the model fit as `well-fitted`, `underfitting`, or `overfitting`.
  - Substantiates the diagnosis with quantitative empirical evidence from the 5-fold temporal cross-validation (`mean ± standard deviation` of MAE and RMSE) and the learning curve convergence pattern.
  - Defines a concrete, model-specific corrective action directly addressing the diagnosed root cause and states a clear recommendation regarding promotion of the model to the staging environment.
- **FR-009**: System MUST include an automated unit test in `tests/pipelines/` that verifies the temporal cross-validation splitter produces at least 5 folds, preserves strict chronological ordering within and across folds (no index or timestamp from a later fold or validation set appears before an earlier training index), and prevents fold overlap or shuffling.
- **FR-010**: All additional package dependencies required for model evaluation, plotting, or testing MUST be managed exclusively via `uv` (`uv add`), without using `pip install` or `pipenv`.

### Key Entities

- **Temporal Cross-Validation Fold**: A single chronological split within the 96-month training window (`2016-01` to `2023-12`) consisting of an expanding historical training subset (`train_indices`) and an immediately following unseen validation subset (`val_indices`), where `max(train_indices) < min(val_indices)`.
- **Fold Evaluation Metrics Summary**: Statistical aggregation recording per-fold and across-fold `mean ± standard deviation` for Training MAE, Validation MAE, Training RMSE, and Validation RMSE in `revenue_eur`.
- **Learning Curve Artifact**: Visual diagnostic plot stored in `data/eval/learning_curve.png` illustrating the progression of training error and validation error as chronological training set size increases across the TrackFlow revenue series.
- **Business Cost Metric Justification (`docs/model-eval.md`)**: Domain-grounded comparative analysis of MAE versus RMSE linking mathematical error weighting to TrackFlow's e-commerce logistics cost structure (overestimation vs. underestimation penalties for warehouse, carrier, and executive stakeholders).
- **Technical Evaluation & Staging Promotion Report (`data/eval/evaluation_report.md`)**: Formal engineering diagnosis classifying model fit (`well-fitted`, `underfitting`, or `overfitting`), documenting empirical cross-validation and learning curve evidence, prescribing a targeted corrective action, and rendering a staging promotion verdict.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Temporal cross-validation executes across at least 5 folds on the 96-month training set with 100% chronological ordering adherence (zero shuffled indices, zero overlapping train/validation timestamps, and zero future feature leakage).
- **SC-002**: Cross-validation evaluation outputs both MAE and RMSE for training and validation sets expressed as `mean ± standard deviation` across all folds, with deterministic reproducibility when using the fixed random seed (`42`).
- **SC-003**: Learning curve visualization is generated and saved in `data/eval/` (`data/eval/learning_curve.png`), clearly plotting both training error and validation error curves across at least 5 increasing training sample sizes.
- **SC-004**: `docs/model-eval.md` is complete, references exact TrackFlow domain entities (`revenue_eur`, `shipments_processed`, `avg_revenue_per_shipment_eur`, `consolidated`, Los Angeles/Zaragoza hubs, November–December +25–35% peaks, February -10–15% dips, and stakeholders Thomas, Ana, and Carlos), compares overestimation vs. underestimation costs, and establishes a primary regression metric between MAE and RMSE.
- **SC-005**: `data/eval/evaluation_report.md` provides an explicit fit classification (`well-fitted`, `underfitting`, or `overfitting`) backed by cross-validation (`mean ± std`) and learning curve numbers, along with a specific, root-cause-aligned corrective action and staging promotion decision.
- **SC-006**: 100% of unit tests in `tests/pipelines/`—including the new chronological fold-ordering verification test and the existing 8/2-year split integrity tests—pass without error.

## Assumptions

- The trained forecasting pipeline and domain modules created in `024-sales-forecasting-regression` (`data/pipelines/sales_forecast/` and `scripts/train_sales_forecast.py`) serve as the baseline model architecture under evaluation (specifically the Random Forest Regressor with `n_estimators=100`, `random_state=42`, and the 12 causal time-series features).
- Both Spanish and English domain contexts in `docs/sales-forecasting/trackflow-BRIEFING.es.md` and `docs/sales-forecasting/trackflow-BRIEFING.en.md` describe the identical `data/raw/trackflow_sales.csv` schema and business dynamics.
- The 2-year hold-out test set (24 months: `2024-01` to `2025-12`) remains untouched during cross-validation fold splitting and hyperparameter/corrective diagnosis, ensuring the 5-fold temporal cross-validation operates strictly within the 8-year (96-month: `2016-01` to `2023-12`) training set.

