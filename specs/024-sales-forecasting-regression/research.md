# Phase 0 Research: Sales Forecasting With a Regression Model

**Feature Branch**: `024-sales-forecasting-regression`  
**Date**: 2026-11-10  
**Status**: Completed  

---

## 1. Algorithm Selection: Random Forest vs. XGBoost

### Decision
Select **Random Forest Regressor** (`sklearn.ensemble.RandomForestRegressor`) as the primary production forecasting algorithm, with benchmark comparison against XGBoost (`xgboost.XGBRegressor`).

### Rationale
1. **Dataset Size (120 monthly records, 96 train, 24 test)**:
   - Gradient boosted trees (XGBoost) are prone to severe overfitting on very small sample sizes ($N=96$) due to sequential gradient optimization unless heavily regularized with conservative hyperparameters (`max_depth=2-3`, `subsample=0.8`, `colsample_bytree=0.8`).
   - Random Forest relies on bagging (Bootstrap Aggregation) and random feature sub-spacing, which naturally reduces variance and is significantly more resilient to small-sample noise without overfitting.
2. **Native Uncertainty & Variability Quantification**:
   - Random Forest is composed of an ensemble of independent estimators (`n_estimators=100+`). The variance/standard deviation across individual tree predictions ($\sigma_{\text{trees}}^2 = \frac{1}{B} \sum_{b=1}^B (\hat{y}_b(x) - \bar{y}(x))^2$) provides an immediate, theoretically sound uncertainty envelope for each forecasted month without requiring external conformal prediction packages or multi-quantile loss retuning.
3. **Executive Explainability (Thomas, CEO & Ana, Warehouse)**:
   - Random Forest feature importances (MDI / permutation importance) provide intuitive insight for operational stakeholders into what drives revenue (e.g., Q4 Black Friday indicator vs. 12-month lag vs. average shipment volume).
4. **Computational & Tuning Budget**:
   - Random Forest converges rapidly with minimal hyperparameter searching and has virtually zero hyperparameter sensitivity compared to gradient boosting learning rates.

### Alternatives Considered
- **XGBoost (`xgboost.XGBRegressor`)**: Evaluated for benchmark comparison. While capable of capturing non-linear interactions, gradient boosting requires careful learning rate tuning (`eta`), tree pruning (`gamma`), and cannot directly produce an internal prediction variance band without training separate quantile regressors ($\alpha=0.05, 0.5, 0.95$).
- **ARIMA / SARIMAX**: Traditional econometric time-series models. Rejected as the primary model because business stakeholders explicitly requested tree-based ensemble regression evaluating shipment volume and pricing dynamics alongside calendar seasonality.

---

## 2. Temporal Partition & Leak-Free Causal Feature Engineering

### Decision
Implement a strict chronological split dividing the consolidated series into:
- **Training Set**: 2016-01-01 to 2023-12-01 (96 months, exactly 8 years).
- **Test Set**: 2024-01-01 to 2025-12-01 (24 months, exactly 2 years).

### Feature Engineering Rules
1. **No Lookahead Bias**:
   - Any rolling window metric (e.g., rolling mean or rolling standard deviation) MUST be shifted by at least 1 month (`df['revenue_eur'].shift(1).rolling(window=3).mean()`).
   - Autoregressive lags MUST use past values: `lag_1` ($t-1$), `lag_2` ($t-2$), `lag_3` ($t-3$), and `lag_12` ($t-12$ capturing year-over-year annual seasonality).
2. **Calendar & Seasonal Indicators**:
   - `month`: Numerical month index (1 to 12).
   - `is_peak_season`: Binary flag for November and December (Black Friday & holiday surge, +25% to +35%).
   - `is_february_dip`: Binary flag for February (-10% to -15% post-holiday e-commerce slowdown).
   - `quarter`: Calendar quarter (Q1–Q4).
   - `annual_trend`: Trend index counter (`t = 0, 1, 2, ...`) capturing structural secular growth.
3. **Leak-Free Scaling**:
   - If feature scaling is applied (e.g. `StandardScaler` or `RobustScaler`), the transformer MUST be fitted exclusively on the 96 training observations:
     ```python
     scaler = StandardScaler()
     X_train_scaled = scaler.fit_transform(X_train)
     X_test_scaled = scaler.transform(X_test)
     ```
   - Test statistics are never exposed during training.

### Alternatives Considered
- **K-Fold Cross-Validation / Random Splitting**: Rejected. Randomly shuffling time series introduces fatal lookahead leakage where future data informs past predictions.
- **Time-Series Rolling Window CV**: Useful for model selection on the training set (e.g., `TimeSeriesSplit(n_splits=4)` on the 96 train months), but final model evaluation strictly uses the hold-out 24 months.

---

## 3. Mathematical Formulations for Evaluation Metrics

### Decision
Implement exact, robust functions for the four required metrics:

#### A. Mean Squared Error (MSE) & Percentage of Mean Revenue
- **MSE Formula**:
  $$\text{MSE} = \frac{1}{N} \sum_{i=1}^{N} (y_i - \hat{y}_i)^2$$
  Reported in $\text{EUR}^2$.
- **Normalized Error (% of Average Revenue)**:
  $$\text{RMSE} = \sqrt{\text{MSE}}$$
  $$\text{Error}_{\%} = \frac{\text{RMSE}}{\bar{y}_{\text{test}}} \times 100\% \quad \text{where } \bar{y}_{\text{test}} = \frac{1}{N} \sum_{i=1}^N y_i$$
  Also calculate direct MSE percentage: $\frac{\text{MSE}}{(\bar{y}_{\text{test}})^2} \times 100\%$ or report Normalized RMSE (NRMSE) so stakeholders have an intuitive percentage representation of error relative to average monthly revenue (~€1.2M - €1.7M).

#### B. Population Stability Index (PSI)
- **Purpose**: Detect whether revenue or feature distributions have drifted between the training period (2016–2023) and the testing period (2024–2025).
- **Formula**:
  $$\text{PSI} = \sum_{k=1}^{K} \left( P_k - Q_k \right) \times \ln\left(\frac{P_k}{Q_k}\right)$$
  Where:
  - $Q_k$ is the baseline/reference proportion (training set distribution binned into $K=5$ or $K=10$ quantile bins).
  - $P_k$ is the target proportion (test set distribution across those same bin edges).
  - Standard Industry Thresholds:
    - $\text{PSI} < 0.10$: Minimal shift, distribution stable.
    - $0.10 \le \text{PSI} < 0.25$: Moderate shift, warrants monitoring.
    - $\text{PSI} \ge 0.25$: Significant distribution shift, model retraining required.

#### C. Gini Coefficient
- **Purpose**: Measure the model's ability to rank-order high-revenue vs. low-revenue periods (seasonal discrimination).
- **Formula**:
  Derived from the Lorenz curve / Area Under the Curve of cumulative predicted vs. actual values:
  $$\text{Gini} = 2 \times \text{AUC}_{\text{Lorenz}} - 1$$
  Or Kendall's / Somers' $D$ rank correlation between predicted and observed rankings. A high Gini confirms that the model reliably ranks November/December above February.

#### D. K2 Score (D'Agostino-Pearson Normality Test)
- **Purpose**: Test model adequacy and residual structure by checking whether residuals $e_i = y_i - \hat{y}_i$ are Gaussian/normally distributed.
- **Formula**:
  $$K^2 = Z_1(s)^2 + Z_2(k)^2$$
  Where $s$ is sample skewness, $k$ is sample kurtosis, and $Z_1, Z_2$ are normal transforms.
  - Implemented via `scipy.stats.normaltest(residuals)`.
  - Returns test statistic $K^2$ and $p$-value. High $p$-value ($p > 0.05$) indicates residuals are consistent with a normal distribution (no unmodeled non-linear patterns or asymmetric systematic bias).

---

## 4. Visual Forecast & Variability Range

### Decision
Plot 2024–2025 actual monthly revenue against predicted revenue with a 95% uncertainty/variability envelope:
- Point prediction: Mean prediction across ensemble trees: $\hat{y}_t = \frac{1}{B} \sum_{b=1}^B \hat{y}_{t,b}$.
- Variability band: $\hat{y}_t \pm 1.96 \times \sigma_t$ where $\sigma_t = \sqrt{\frac{1}{B-1} \sum_{b=1}^B (\hat{y}_{t,b} - \hat{y}_t)^2 + \text{MSE}_{\text{train}}}$.
- Visual components:
  1. Solid dark line with markers for ground truth actual test revenue.
  2. Dashed or contrasting solid line for predicted revenue.
  3. Semi-transparent shaded ribbon indicating the $\pm 1.96\sigma$ uncertainty envelope.
  4. Callouts/annotations for November-December seasonal peaks and February dips.
  5. Saved as `reports/sales_forecast_test_eval.png` (high-res 300 DPI).

---

## 5. Technology Stack & Dependencies

### Decision
- **Environment & Package Manager**: `uv` (isolated virtual environment in `services/api/.venv` or dedicated pipeline venv).
- **Core Libraries**:
  - `pandas>=3.0` & `numpy>=2.5`: Data manipulation, temporal lagging, rolling calculations.
  - `scikit-learn`: `RandomForestRegressor`, `StandardScaler`, metrics.
  - `scipy`: `scipy.stats.normaltest` (K2 test), `scipy.stats` for distributions.
  - `matplotlib` & `seaborn`: High-resolution chart rendering.
  - `pytest`: Automated pipeline validation tests.

