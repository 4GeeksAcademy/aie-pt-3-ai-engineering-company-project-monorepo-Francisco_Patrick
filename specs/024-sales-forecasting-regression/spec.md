# Feature Specification: Sales Forecasting With a Regression Model

**Feature Branch**: `024-sales-forecasting-regression`

**Created**: 2026-11-10

**Status**: Draft

**Input**: User description: "/speckit-specify # Feature: Sales Forecasting With a Regression Model"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Time-Series Revenue Forecasting Baseline & Split Integrity (Priority: P1)

Finance and executive leadership (CEO Thomas) need a strictly validated historical time-series split—training the model on the first 8 years of historical sales (2016–2023) and evaluating it strictly against the 2 most recent unseen years (2024–2025)—to test whether future revenue volume is predictable before committing to a full executive dashboard investment.

**Why this priority**: Split integrity is the non-negotiable foundation of time-series modeling. Any lookahead bias, random shuffle, or data leakage from the evaluation window into the training window produces false predictive confidence and invalidates executive decision-making.

**Independent Test**: Can be fully tested by running the data partitioning and feature scaling routine against `data/raw/trackflow_sales.csv` and verifying that training strictly comprises the first 96 months (2016-01 to 2023-12) and evaluation strictly comprises the subsequent 24 months (2024-01 to 2025-12) with zero data overlap.

**Acceptance Scenarios**:

1. **Given** the historical sales dataset with 120 consecutive consolidated monthly records from 2016-01 to 2025-12, **When** the dataset split function executes, **Then** exactly the first 8 years (96 months) are assigned to training and the final 2 years (24 months) are assigned to testing with chronological order strictly preserved.
2. **Given** features requiring normalization or scaling, **When** scaling transformers are fitted, **Then** statistics (mean, variance, min/max) are computed strictly from the 96-month training set and applied forward to the test set without leaking test distribution parameters.

---

### User Story 2 - Stakeholder Multi-Metric Model Evaluation (Priority: P2)

Finance stakeholders and operational leadership (Warehouse and Carrier leads) need an evaluation report that assesses model performance across four distinct dimensions—Mean Squared Error (MSE), Population Stability Index (PSI), Gini coefficient, and K2 Score—to understand predictive accuracy, distributional stability, seasonal rank-ordering, and residual normality.

**Why this priority**: A low MSE alone is insufficient for financial planning; stakeholders must know whether prediction errors reflect post-peak structural shifts (PSI), whether high and low seasons are reliably separated (Gini), and whether residual errors satisfy statistical adequacy (K2 Score).

**Independent Test**: Can be tested independently by evaluating model predictions on the 24-month test set and asserting that all four metrics are calculated, formatted for non-technical stakeholders (including MSE in both EUR² and percentage of average monthly revenue), and documented with clear business interpretations.

**Acceptance Scenarios**:

1. **Given** a trained regression model and the 24-month unseen test dataset, **When** evaluation execution completes, **Then** MSE, PSI, Gini coefficient, and K2 Score are computed solely on the test set and reported in the evaluation summary.
2. **Given** the final evaluation summary, **When** reviewed by Finance, **Then** MSE is expressed both in absolute EUR² and as a percentage of average monthly revenue, accompanied by documented rationales explaining why low MSE alone does not guarantee model reliability.

---

### User Story 3 - Visual Revenue Forecast with Uncertainty & Variability Range (Priority: P3)

Finance leadership requires an intuitive visual representation of the forecasted sales trajectory comparing predicted revenue against actual observed revenue across the 24 test months, displaying a shaded variability/uncertainty range rather than a single point estimate.

**Why this priority**: Financial budgeting and carrier capacity planning require risk boundaries. Single point estimates hide volatility, whereas a variability range equips planners with upper and lower revenue bands to navigate peak and post-peak periods.

**Independent Test**: Can be tested independently by generating the forecast visualization artifact and verifying that it renders the test timeline, actual revenue, forecasted revenue, and an explicit variability envelope covering seasonal fluctuations (such as November–December peaks and February dips).

**Acceptance Scenarios**:

1. **Given** model predictions and variance/variability estimations for the 24 test months, **When** the visualization script executes, **Then** it produces a chart plotting actual sales, predicted sales, and an uncertainty band across the entire 2024–2025 timeline.
2. **Given** historical seasonal patterns (25–35% surge in Nov–Dec, 10–15% drop in Feb), **When** inspecting the generated visualization, **Then** the predicted trajectory and variability boundaries reflect these cyclical dynamics without temporal lag or trend distortion.

---

### User Story 4 - Algorithmic Selection & Trade-Off Documentation (Priority: P4)

Technical and business decision-makers require an explicit written justification in Spanish (`docs/training-model-decission.md`) detailing the selection between Random Forest and XGBoost based on dataset size, explainability, and tuning constraints.

**Why this priority**: Documents the architectural rationale for executive stakeholders and ensures future engineering teams understand why the chosen algorithm best fits TrackFlow's operational scale and explainability requirements.

**Independent Test**: Can be tested independently by verifying the existence and contents of `docs/training-model-decission.md`, confirming that it articulates trade-offs in Spanish regarding data volume (120 observations), explainability, and computational overhead.

**Acceptance Scenarios**:

1. **Given** the completed model implementation, **When** checking `docs/training-model-decission.md`, **Then** the document is present in Spanish and comprehensively details why Random Forest or XGBoost was chosen against criteria of dataset size, explainability, and tuning time.

---

### Edge Cases

- **Missing or Corrupted Monthly Records**: If `data/raw/trackflow_sales.csv` contains missing dates, gaps in sequence, or non-positive revenue values, the data ingestion pipeline must reject the payload or log descriptive errors before partitioning.
- **Null or Empty Values**: Any null values in input features or target columns must be identified and handled deterministically prior to model training.
- **Distribution Shift Across Markets**: If operational volume between Los Angeles and Zaragoza shifts materially between training (2016–2023) and test (2024–2025), PSI must flag the divergence to prevent unwarranted confidence in consolidated aggregates.
- **Feature Scaling Leaks**: Scaling transformations applied across features with divergent scales (such as total revenue in €100k+ vs unit rate in €10–20) must strictly avoid using test dataset statistics.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST verify the existence of `data/raw/trackflow_sales.csv` and validate that its column schema matches `docs/sales-forecasting/trackflow-BRIEFING.en.md` (`month`, `revenue_eur`, `shipments_processed`, `avg_revenue_per_shipment_eur`, `market`).
- **FR-002**: System MUST isolate and utilize the `consolidated` market rows for training and evaluating the primary revenue forecasting model.
- **FR-003**: System MUST identify and handle null or empty values prior to feature engineering and model training.
- **FR-004**: System MUST partition the time series chronologically into a training set comprising the first 8 years (2016-01-01 to 2023-12-01, 96 monthly observations) and a test set comprising the final 2 years (2024-01-01 to 2025-12-01, 24 monthly observations).
- **FR-005**: System MUST fit all feature transformers (including scaling of numeric variables having disparate magnitudes) strictly on the training set and transform the test set without lookahead leakage.
- **FR-006**: System MUST engineer causal features (such as calendar month indicators, seasonal markers, and historical lags) without utilizing future observations from subsequent rows.
- **FR-007**: System MUST train an ensemble regression model using either **Random Forest** or **XGBoost** with a fixed random seed (`random_state`/`seed`) for reproducible execution.
- **FR-008**: System MUST document the algorithm selection justification in Spanish at `docs/training-model-decission.md`, analyzing dataset size (120 monthly observations), need for stakeholder explainability, and available tuning budget.
- **FR-009**: System MUST evaluate the model strictly on the 24-month out-of-sample test set, calculating and reporting:
  - Mean Squared Error (**MSE**), reported in EUR² and as a percentage of average monthly revenue.
  - Population Stability Index (**PSI**), assessing distributional shift between training and test periods.
  - **Gini** coefficient, quantifying seasonal discrimination and ranking accuracy.
  - **K2 Score** (D'Agostino-Pearson normality test / model adequacy on residuals).
- **FR-010**: System MUST document the interpretation of each metric in the implementation documentation or code comments, explicitly clarifying why a low MSE alone does not guarantee model suitability for financial risk management.
- **FR-011**: System MUST generate a forecast visualization displaying predicted monthly revenue along with an estimated variability/uncertainty envelope, plotted alongside ground-truth test data for the 2024–2025 period.
- **FR-012**: System MUST implement an automated unit test in `tests/pipelines/` verifying that the 8-year / 2-year temporal partition respects chronological boundaries and introduces zero data leakage.
- **FR-013**: System MUST manage all Python runtime dependencies exclusively using `uv` (avoiding global or direct `pip`).

### Key Entities

- **Monthly Consolidated Revenue Observation**: Primary historical record comprising `month`, `revenue_eur`, `shipments_processed`, `avg_revenue_per_shipment_eur`, and `market`.
- **Temporal Partition**: Explicit split dividing the 120-month continuous time series into an 8-year training window (96 months) and a 2-year evaluation window (24 months).
- **Model Evaluation Summary**: Structured report encapsulating test set metrics (MSE in EUR², MSE as % of mean revenue, PSI, Gini, and K2 Score) alongside qualitative business risk interpretations.
- **Variability Forecast**: Forecast representation delivering point estimates accompanied by lower and upper uncertainty bounds per forecasted period.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Temporal data split achieves 100% adherence: exactly 96 training months (2016–2023) and 24 test months (2024–2025), with zero test rows exposed during training or feature scaling.
- **SC-002**: Automated unit test in `tests/pipelines/` passes with 100% success rate, validating partition sizing and zero overlap between train and test intervals.
- **SC-003**: 100% of required evaluation metrics (MSE in EUR² and % of revenue, PSI, Gini, K2 Score) are calculated and reported on the test set.
- **SC-004**: Prediction visualization clearly renders the test timeline, actual revenue points, predicted revenue points, and an explicit uncertainty band spanning all 24 evaluation months.
- **SC-005**: All pipeline runs initialized with the designated random seed generate deterministic, reproducible training and evaluation outputs.
- **SC-006**: Complete business justification document exists at `docs/training-model-decission.md` written in Spanish detailing the algorithm selection criteria.

## Assumptions

- The raw dataset at `data/raw/trackflow_sales.csv` contains uninterrupted monthly records from 2016-01-01 to 2025-12-01 with `consolidated` as the primary market tag.
- The variability range for the forecast visualization can be derived using ensemble tree variance, residual standard error, or quantile estimation appropriate to the chosen model architecture.
- Downstream executive dashboard integration is subject to feasibility approval from Finance based on the metrics and visual clarity delivered by this proof-of-concept pipeline.
- Python dependencies are installed and isolated via `uv` virtual environments as per repository standards.

