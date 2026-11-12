# Phase 0 Research: Regression Model Evaluation

**Feature Branch**: `025-regression-model-evaluation`  
**Date**: 2026-11-12  
**Status**: Completed  

---

## 1. Temporal Cross-Validation Strategy Without Leakage

### Decision
Implement an **Expanding-Window Chronological Cross-Validation Splitter** (`TimeSeriesSplit(n_splits=5)` / custom deterministic expanding-window fold generator) strictly confined to the 8-year (96-month: `2016-01-01` to `2023-12-01`) consolidated training partition, keeping the 2-year hold-out test set (24 months: `2024-01-01` to `2025-12-01`) completely untouched.

### Rationale
1. **Strict Chronological Causality ($N_{\text{train}} = 96$ months)**:
   - Time-series observations exhibit serial autocorrelation (`lag_1`, `lag_2`, `lag_3`, `lag_12`), secular annual growth (alternating between $3\%$ and $9\%$ around a $6\%$ base), and deterministic calendar seasonality (+25–35% in November–December, -10–15% in February).
   - Standard random $K$-Fold (`KFold(shuffle=True)` or `KFold(shuffle=False)` where future folds train on years 2020–2023 to predict 2016–2017) violates causality and leaks future secular growth levels and rolling statistics backward into earlier periods.
2. **Fold Sizing Across 96 Months (5 Folds)**:
   - With $N = 96$ training months and $K = 5$ chronological folds (`n_splits=5`), each validation fold spans $16$ consecutive months ($\lfloor 96 / (5 + 1) \rfloor = 16$):
     - **Fold 1**: Train indices `[0..15]` (`2016-01` to `2017-04`, 16 months) $\rightarrow$ Val indices `[16..31]` (`2017-05` to `2018-08`, 16 months)
     - **Fold 2**: Train indices `[0..31]` (`2016-01` to `2018-08`, 32 months) $\rightarrow$ Val indices `[32..47]` (`2018-09` to `2019-12`, 16 months)
     - **Fold 3**: Train indices `[0..47]` (`2016-01` to `2019-12`, 48 months) $\rightarrow$ Val indices `[48..63]` (`2020-01` to `2021-04`, 16 months)
     - **Fold 4**: Train indices `[0..63]` (`2016-01` to `2021-04`, 64 months) $\rightarrow$ Val indices `[64..79]` (`2021-05` to `2022-08`, 16 months)
     - **Fold 5**: Train indices `[0..79]` (`2016-01` to `2022-08`, 80 months) $\rightarrow$ Val indices `[80..95]` (`2022-09` to `2023-12`, 16 months)
   - Every validation window spans $16$ months ($\ge 1$ full annual seasonal cycle, guaranteeing inclusion of at least one Peak Season or February Dip window) while ensuring `max(train_indices) < min(val_indices)` for all folds.
3. **Fold-Isolated Feature Engineering & Scaling**:
   - Within each fold $k \in \{1 \dots 5\}$, causal features (`build_causal_feature_matrix`) are constructed from the fold's visible slice `train_df.iloc[:val_end + 1]` so that:
     - Initial-value lag imputation (`first_val = rev.iloc[0]`) depends exclusively on `2016-01-01` (index 0).
     - `StandardScaler` is fitted **strictly** on `X_fold_train` (`scaler.fit_transform(X_fold_train)`) and applied via `scaler.transform(X_fold_val)`. No validation or hold-out test statistics ever enter scaler mean/variance parameters.

### Alternatives Considered
- **Standard K-Fold (`KFold(n_splits=5)`)**: Rejected because training on later years to validate on earlier years reverses the arrow of time and leaks secular trend and rolling window context.
- **Sliding Fixed-Window Split**: Rejected because restricting early training windows to a fixed 16-month sliding slice discards valuable multi-year seasonal history needed by Random Forest trees to estimate year-over-year `lag_12` relationships.

---

## 2. Error Metrics & Business Cost Asymmetry (MAE vs. RMSE)

### Decision
Compute both **MAE** (Mean Absolute Error) and **RMSE** (Root Mean Squared Error) in EUR (`revenue_eur`) across training and validation sets for every fold, report them as `mean ± standard deviation`, and establish **RMSE** as the primary decision metric (paired with MAE as an operational baseline interpretation metric) in `docs/model-eval.md`.

### Mathematical Formulations
- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |y_i - \hat{y}_i|$$
  Weights all errors linearly in EUR. Represents the typical monthly deviation in billing volume.
- **Root Mean Squared Error (RMSE)**:
  $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (y_i - \hat{y}_i)^2}$$
  Squares residuals before averaging, penalizing large outlier errors quadratically in EUR.
- **Cross-Fold Aggregation**:
  $$\mu_{\text{metric}} = \frac{1}{K} \sum_{k=1}^{K} m_k, \quad \sigma_{\text{metric}} = \sqrt{\frac{1}{K - 1} \sum_{k=1}^{K} (m_k - \mu_{\text{metric}})^2}$$
  Reported as `mean ± std` (sample standard deviation with `ddof=1`).

### Business Cost Justification (TrackFlow Operational Context)
1. **Underestimation Risk (Actual Revenue > Predicted Revenue — Peak Capacity Shortfall)**:
   - **Ana (Warehouse Operations)**: Underestimating November–December Black Friday / Christmas peaks (+25–35% surge) leads to severe warehouse understaffing and packaging material stockouts in Los Angeles (60% volume) and Zaragoza (40% volume), causing SLA breaches, delayed e-commerce fulfillment, overtime emergency labor premiums, and client churn.
   - **Carlos (Carrier Management)**: Failing to lock in carrier volume commitments ahead of Q4 peak season forces TrackFlow to purchase spot-market freight capacity at steep surcharges.
2. **Overestimation Risk (Predicted Revenue > Actual Revenue — Idle Resource Allocation)**:
   - **Ana & Carlos**: Overestimating monthly shipment volume (`shipments_processed`) during normal months or the February post-holiday dip (-10–15%) results in idle temporary warehouse shifts, excess packaging inventory carrying costs, and unused minimum-volume carrier contract penalties.
   - **Thomas (CEO)**: Overestimating baseline revenue masks structural operational contractions, whereas uncalibrated error spikes prevent distinguishing a normal February seasonal trough from an acute regional outage in the US or Spain hubs.
3. **Why RMSE vs. MAE Matters**:
   - Because catastrophic misses during peak e-commerce surges (November–December) inflict disproportionately higher financial and SLA damage (spot carrier rates, emergency overtime, brand penalties) than routine $\pm 5\%$ monthly fluctuations, **RMSE** is selected as the **primary staging gate metric** because its quadratic penalty heavily penalizes large peak-season errors. **MAE** is retained as the secondary executive communication metric because it expresses the typical linear EUR error per month without distortion from single-month spikes.

---

## 3. Learning Curve Design & Model Fit Diagnosis

### Decision
Generate the learning curve (`data/eval/learning_curve.png`) by evaluating the baseline `RandomForestRegressor(n_estimators=100, random_state=42)` across increasing chronological training subset sizes derived from the 5 expanding folds (or 5+ monotonically increasing chronological training windows from $16$ to $80$ months), plotting both Training Error and Validation Error (MAE and RMSE panels or primary RMSE with MAE overlay/band) against training sample size $N_{\text{train}}$.

### Empirical Diagnosis of Baseline Model (`RandomForestRegressor(n_estimators=100, random_state=42)`)
1. **Observed Behavior on TrackFlow 96-Month Training Series**:
   - **Unconstrained Tree Depth**: The baseline model in `data/pipelines/sales_forecast/model.py` uses default `max_depth=None` and `min_samples_leaf=1`. On small chronological training subsets ($N = 16 \dots 80$), unconstrained decision trees memorize the historical training points (`Training MAE / RMSE` remains very low, approximately one-third of validation error), while `Validation MAE / RMSE` remains substantially higher with a persistent generalization gap across all 5 folds.
   - **Step-Function Extrapolation Ceiling on Secular Trend**: Because TrackFlow's revenue grows by $6\% \pm 3\%$ annually (`trend_index` and `lag_1` increase monotonically over time), each validation fold $k$ occupies a higher revenue regime than its preceding training window $[0 \dots t_k]$. Decision trees in a Random Forest cannot extrapolate linear trends beyond the maximum target value observed in `y_train`, causing systematic under-prediction on the upper end of each expanding validation fold and elevated validation RMSE (`mean ± std`).
2. **Formal Fit Classification**:
   - The baseline unconstrained Random Forest exhibits **overfitting** (high variance on in-sample training partitions coupled with a wide, persistent training-to-validation error gap and secular trend boundary bias on out-of-sample folds).
3. **Root-Cause-Driven Corrective Action**:
   - **Primary Root Cause 1 (Tree Memorization / Variance)**: Unconstrained depth (`max_depth=None`, `min_samples_leaf=1`) on $N \le 80$ rows allows leaves to isolate single months.
   - **Primary Root Cause 2 (Non-Stationary Secular Trend Extrapolation)**: Tree ensembles predict constants within terminal leaves and cannot extrapolate the $6\% \pm 3\%$ compounding annual growth trend into unseen future folds.
   - **Targeted Corrective Action**:
     1. Apply structural tree regularization (`max_depth=4`, `min_samples_leaf=2`, `min_samples_split=4`) to constrain leaf granularity and close the variance gap between training and validation curves; **AND**
     2. Detrend target revenue via a causal linear trend baseline (or switch to a Ridge/ElasticNet-detrended hybrid or year-over-year relative growth ratio $y_t / y_{t-12}$) before fitting the Random Forest on the seasonal residuals.

---

## 4. Architecture & Module Integration

### Decision
Extend the existing `data/pipelines/sales_forecast/` package and `scripts/` without breaking any `024-sales-forecasting-regression` contracts or tests:
- Add `data/pipelines/sales_forecast/evaluator.py` (or extend `dataset.py`, `metrics.py`, `visualizer.py`) to encapsulate:
  - `create_temporal_cv_splits(df, n_splits=5)`: Returns 5 strictly chronological `TemporalCVFold` objects on the 96-month training partition with automated leakage guards.
  - `evaluate_temporal_cv(df, n_splits=5, random_seed=42)`: Runs leak-free per-fold feature engineering, train-only `StandardScaler` fitting, model training, and computes per-fold and aggregate (`mean ± std`) Training & Validation MAE and RMSE.
  - `compute_learning_curve(df, n_splits=5, random_seed=42)` & `render_learning_curve(result, output_path="data/eval/learning_curve.png")`: Generates the high-resolution learning curve chart in `data/eval/learning_curve.png`.
  - `classify_model_fit(cv_summary, learning_curve)` & `generate_evaluation_report(summary, output_path="data/eval/evaluation_report.md")`: Produces the formal markdown report in `data/eval/evaluation_report.md` and `docs/model-eval.md`.
- Add CLI entry point `scripts/evaluate_sales_forecast.py` (and integrate optional evaluation flags) to execute the full 5-fold cross-validation, learning curve plotting, and report generation deterministically.
- Add unit tests in `tests/pipelines/test_regression_evaluation.py` (and/or `tests/pipelines/test_sales_forecast.py`) specifically verifying chronological fold ordering, zero overlap, zero feature/scaler leakage, and artifact generation.

---

## 5. Dependencies & Environment Management

### Decision
Reuse the existing `uv`-managed environment in `services/api` (`scikit-learn`, `scipy`, `pandas`, `numpy`, `matplotlib`, `pytest`). No global `pip` installations are permitted (`FR-010`). If any package is ever added, it must use `uv add --project services/api`.

