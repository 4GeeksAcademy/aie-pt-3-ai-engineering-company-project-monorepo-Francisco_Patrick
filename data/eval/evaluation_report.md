# Technical Evaluation & Model Fit Diagnosis Report

**Model Under Evaluation**: `RandomForestRegressor(n_estimators=100, random_state=42)`  
**Dataset**: `data/raw/trackflow_sales.csv` (`market == "consolidated"`, target `revenue_eur`)  
**Evaluation Partition**: 8-Year Historical Training Window (`2016-01-01` to `2023-12-01`, 96 months)  
**Hold-Out Test Partition**: 2-Year Unseen Test Window (`2024-01-01` to `2025-12-01`, 24 months — **Strictly Isolated / Untouched**)  
**Cross-Validation Strategy**: 5-Fold Expanding-Window Chronological Split (Zero Lookahead Leakage)  

---

## 1. Executive Diagnosis & Staging Readiness Verdict

| Evaluation Dimension | Result / Verdict |
|---|---|
| **Explicit Model Fit Classification** | **`overfitting`** |
| **Primary Decision Metric** | **RMSE** (Root Mean Squared Error in `revenue_eur`) |
| **Cross-Validation Training MAE (`mean ± std`)** | **€16,070.19 ± €3,064.67** |
| **Cross-Validation Validation MAE (`mean ± std`)** | **€67,850.89 ± €24,590.22** |
| **Cross-Validation Training RMSE (`mean ± std`)** | **€21,209.75 ± €4,681.47** |
| **Cross-Validation Validation RMSE (`mean ± std`)** | **€79,883.94 ± €27,547.27** |
| **Validation-to-Training RMSE Gap Ratio** | **3.77x** (Validation NRMSE: **8.19%** of mean revenue) |
| **Staging Promotion Recommendation** | **`HOLD_REQUIRES_REMEDIATION`** |

---

## 2. Multi-Fold Temporal Cross-Validation Results (`mean ± std`)

To verify whether the baseline forecasting pipeline generalizes across TrackFlow's alternating high-growth ($9\%$) and low-growth ($3\%$) annual cycles without peeking into future data, the 96-month training dataset (`2016-01-01` to `2023-12-01`) was partitioned into **5 expanding chronological folds**. Within every fold $k \in \{1 \dots 5\}$:
1. Causal lag features (`lag_1`, `lag_2`, `lag_3`, `lag_12`), rolling window statistics (`rolling_mean_3`, `rolling_mean_6`, `rolling_std_3`), and calendar indicators (`month_num`, `quarter`, `is_peak_season`, `is_february_dip`, `trend_index`) were computed strictly on the visible historical slice up to the fold boundary.
2. `StandardScaler` was fitted **exclusively** on the fold's historical training rows (`X_fold_train`) and applied to `X_fold_val`.

### 2.1 Per-Fold Breakdown

| Fold | Training Window ($N_{\text{train}}$) | Validation Window ($N_{\text{val}}$) | Train MAE (EUR) | Val MAE (EUR) | Train RMSE (EUR) | Val RMSE (EUR) | Mean Val Revenue (EUR) |
|---|---|---|---|---|---|---|---|
| **Fold 1** | `2016-01-01 to 2017-04-01` (16m) | `2017-05-01 to 2018-08-01` (16m) | €21,295.84 | €42,022.88 | €29,232.83 | €52,882.05 | €852,387.62 |
| **Fold 2** | `2016-01-01 to 2018-08-01` (32m) | `2018-09-01 to 2019-12-01` (16m) | €13,675.59 | €89,277.94 | €18,883.79 | €103,645.98 | €956,013.67 |
| **Fold 3** | `2016-01-01 to 2019-12-01` (48m) | `2020-01-01 to 2021-04-01` (16m) | €14,220.67 | €45,580.65 | €17,848.41 | €52,043.55 | €981,004.45 |
| **Fold 4** | `2016-01-01 to 2021-04-01` (64m) | `2021-05-01 to 2022-08-01` (16m) | €15,020.51 | €66,339.44 | €18,652.91 | €79,874.24 | €1,069,331.54 |
| **Fold 5** | `2016-01-01 to 2022-08-01` (80m) | `2022-09-01 to 2023-12-01` (16m) | €16,138.36 | €96,033.55 | €21,430.83 | €110,973.89 | €1,202,304.47 |
| **Aggregate (`mean ± std`)** | **16 → 80 months** | **16 months / fold** | **€16,070.19 ± €3,064.67** | **€67,850.89 ± €24,590.22** | **€21,209.75 ± €4,681.47** | **€79,883.94 ± €27,547.27** | — |

---

## 3. Learning Curve Analysis & Empirical Evidence of `overfitting`

The learning curve artifact saved at `data/eval/learning_curve.png` plots in-sample Training Error and out-of-sample Validation Error (both MAE and RMSE) across increasing chronological training sample sizes ($N_{\text{train}} = 16, 32, 48, 64, 80$ months).

### 3.1 Learning Curve Trajectory Table

| Training Sample Size ($N_{\text{train}}$) | Training MAE (EUR) | Validation MAE (EUR) | Training RMSE (EUR) | Validation RMSE (EUR) | Generalization Gap RMSE (EUR) | Val / Train RMSE Ratio |
|---|---|---|---|---|---|---|
| **16 months** | €21,295.84 | €42,022.88 | €29,232.83 | €52,882.05 | €23,649.22 | 1.81x |
| **32 months** | €13,675.59 | €89,277.94 | €18,883.79 | €103,645.98 | €84,762.19 | 5.49x |
| **48 months** | €14,220.67 | €45,580.65 | €17,848.41 | €52,043.55 | €34,195.14 | 2.92x |
| **64 months** | €15,020.51 | €66,339.44 | €18,652.91 | €79,874.24 | €61,221.33 | 4.28x |
| **80 months** | €16,138.36 | €96,033.55 | €21,430.83 | €110,973.89 | €89,543.06 | 5.18x |

### 3.2 Quantitative Justification of Model Fit Classification (`overfitting`)

Across the 5 expanding chronological folds (training sizes N = 16, 32, 48, 64, 80 months), in-sample Training RMSE averages €21,209.75 ± €4,681.47 (2.17% of mean revenue) and Training MAE averages €16,070.19 ± €3,064.67, whereas out-of-sample Validation RMSE jumps to €79,883.94 ± €27,547.27 (8.19% of mean revenue) and Validation MAE reaches €67,850.89 ± €24,590.22. This yields a 3.77x validation-to-training RMSE ratio (4.22x MAE ratio). On the learning curve, as training history expands from N=16 (Train RMSE €29,232.83 vs. Val RMSE €52,882.05, gap 1.81x) to N=80 (Train RMSE €21,430.83 vs. Val RMSE €110,973.89, gap 5.18x), in-sample training error stays depressed near ~€18k–€29k while out-of-sample validation error widens to €110,973.89 as nominal revenue grows across years, leaving an unclosed generalization gap of €89,543.06 (5.18x).

Key diagnostic observations from the learning curve (`data/eval/learning_curve.png`):
- **Persistently Low In-Sample Training Error**: Across all 5 chronological sample sizes, Training RMSE remains tightly bounded between **€29,232.83** and **€21,430.83** (`€21,209.75 ± €4,681.47`), demonstrating that the unconstrained Random Forest memorizes historical training observations.
- **Wide Generalization Gap Across Folds**: Out-of-sample Validation RMSE averages **€79,883.94 ± €27,547.27**—more than **3.77x** higher than Training RMSE. Even at the largest training window ($N = 80$ months in Fold 5), Validation RMSE (**€110,973.89**) remains **5.18x** above Training RMSE (**€21,430.83**).
- **Cross-Fold Growth Regime & Seasonal Variance**: Across the 5 folds, Validation RMSE fluctuates with a standard deviation of **€27,547.27** (ranging from **€52,043.55** in Fold 3 to **€110,973.89** in Fold 5). Folds whose validation windows encompass high-growth ($9\%$) Q4 holiday surges (Fold 2 in `2018-09`–`2019-12` at **€103,645.98** and Fold 5 in `2022-09`–`2023-12` at **€110,973.89**) suffer severe step-function boundary bias because decision tree leaves cannot predict above the historical training maximum, whereas Training RMSE stays artificially low (**€21,430.83**) due to unconstrained tree memorization.

---

## 4. Root-Cause Diagnosis & Concrete Corrective Action

### 4.1 Diagnosed Root Cause

Two coupled mechanisms in the baseline RandomForestRegressor(n_estimators=100, max_depth=None, min_samples_leaf=1) drive this overfitting pattern on the 96-month series: (1) Unconstrained Tree Depth & Single-Sample Leaves — with default max_depth=None and min_samples_leaf=1 on compact monthly windows (16 to 80 observations), individual decision trees partition the feature space until terminal leaves isolate single historical months, memorizing in-sample noise (±5% monthly fluctuations) and driving Training RMSE down to ~3% of revenue; and (2) Step-Function Extrapolation Ceiling on Non-Stationary Secular Growth — TrackFlow's consolidated revenue compounds at 6% ± 3% annually (alternating 3% and 9% growth years), meaning every chronological validation fold operates in a higher nominal EUR regime than its preceding training window, and tree ensembles cannot extrapolate linear trends beyond the maximum y_train value observed during training (causing systematic peak under-prediction during November–December +25–35% surges).

### 4.2 Concrete, Root-Cause-Aligned Corrective Action

Implement a two-part remediation before promoting the model to the staging environment: (1) Structural Tree Regularization — constrain tree complexity by setting max_depth=4, min_samples_leaf=2, and min_samples_split=4 (or max_features='sqrt') in RandomForestRegressor so terminal leaves average across multiple seasonal cycles rather than memorizing individual months; and (2) Causal Linear Trend Detrending — fit a causal linear trend baseline (Ridge/OLS on trend_index fitted strictly within each fold's training window) or transform the target into year-over-year relative ratios (y_t / lag_12) prior to fitting the Random Forest on the stationary seasonal residuals, eliminating the step-function extrapolation ceiling on compounding 3%–9% annual revenue growth.

| Remediation Axis | Baseline Configuration | Prescribed Remediation | Expected Impact on Learning Curve |
|---|---|---|---|
| **1. Tree Depth & Leaf Regularization** | `max_depth=None`, `min_samples_leaf=1`, `min_samples_split=2` | Set `max_depth=4`, `min_samples_leaf=2`, `min_samples_split=4` in `RandomForestRegressor` | Raises in-sample Training RMSE moderately while reducing out-of-sample Validation RMSE variance across folds, compressing the `3.77x` generalization gap. |
| **2. Secular Growth Extrapolation** | Raw `revenue_eur` target predicted directly by step-function tree leaves | Fit a causal linear trend baseline (`Ridge` / `LinearRegression` on `trend_index` fitted strictly on `X_fold_train`) and train the Random Forest on the detrended seasonal residuals $r_t = y_t - \hat{y}_{\text{trend}, t}$ | Eliminates systematic under-prediction when validation folds enter higher nominal EUR regimes driven by the $6\% \pm 3\%$ compounding annual growth trend. |

---

## 5. Staging Promotion Recommendation

**Verdict**: **`HOLD_REQUIRES_REMEDIATION`**

While the pipeline's chronological partitioning, causal feature engineering, and per-fold `StandardScaler` isolation pass 100% of data leakage audits, promoting the unregularized, non-detrended baseline `RandomForestRegressor` directly to staging would expose TrackFlow operations (Ana in Warehouse Operations and Carlos in Carrier Management) to a **€79,883.94 ± €27,547.27** validation RMSE (**8.19%** of mean revenue), primarily concentrated in peak Q4 months where tree step-functions cap revenue forecasts at historical maximums. Engineering should apply the prescribed **tree depth regularization (`max_depth=4, min_samples_leaf=2`) + causal linear trend detrending** and re-run `scripts/evaluate_sales_forecast.py` to confirm gap convergence before staging promotion.
