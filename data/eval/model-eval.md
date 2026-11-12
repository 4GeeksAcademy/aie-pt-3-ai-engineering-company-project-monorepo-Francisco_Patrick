# Business Cost & Error Metric Justification: MAE vs. RMSE

**Feature**: `025-regression-model-evaluation`  
**Target Variable**: `revenue_eur` (`market == "consolidated"` in `data/raw/trackflow_sales.csv`)  
**Operational Volume Drivers**: `shipments_processed` and `avg_revenue_per_shipment_eur` (~€14.91/shipment across **Los Angeles [US, 60% volume]** and **Zaragoza [Spain, 40% volume]**)  
**Primary Decision Metric Selected**: **RMSE (Root Mean Squared Error)** (paired with **MAE** as secondary linear executive interpretation metric)  

---

## 1. Empirical Training & Validation Error Summary (5-Fold Temporal Cross-Validation)

Evaluated strictly across **5 expanding chronological folds** within the 8-year training partition (`2016-01-01` to `2023-12-01`, 96 months, keeping the 2024–2025 hold-out test set untouched), the baseline `RandomForestRegressor(n_estimators=100, random_state=42)` achieves the following error distributions:

| Metric | Training Set (`mean ± std`) | Validation Set (`mean ± std`) | Equivalent Shipment Volume Error (`val mean`) | Mathematical Weighting |
|---|---|---|---|---|
| **MAE (Mean Absolute Error)** | **€16,070.19 ± €3,064.67** | **€67,850.89 ± €24,590.22** | ~**4,549 shipments/month** | Linear penalty: $\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} \|y_i - \hat{y}_i\|$ |
| **RMSE (Root Mean Squared Error)** | **€21,209.75 ± €4,681.47** | **€79,883.94 ± €27,547.27** | ~**5,356 shipments/month** (3,214 LA / 2,142 Zaragoza) | Quadratic outlier penalty: $\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (y_i - \hat{y}_i)^2}$ |

### Per-Fold MAE vs. RMSE Comparison Across Expanding Windows

| Chronological Fold (Validation Period) | Train MAE (EUR) | Val MAE (EUR) | Train RMSE (EUR) | Val RMSE (EUR) | Val RMSE − Val MAE Outlier Spread |
|---|---|---|---|---|---|
| **Fold 1** (`2017-05-01 to 2018-08-01`) | €21,295.84 | €42,022.88 | €29,232.83 | €52,882.05 | €10,859.17 (1.26x) |
| **Fold 2** (`2018-09-01 to 2019-12-01`) | €13,675.59 | €89,277.94 | €18,883.79 | €103,645.98 | €14,368.04 (1.16x) |
| **Fold 3** (`2020-01-01 to 2021-04-01`) | €14,220.67 | €45,580.65 | €17,848.41 | €52,043.55 | €6,462.90 (1.14x) |
| **Fold 4** (`2021-05-01 to 2022-08-01`) | €15,020.51 | €66,339.44 | €18,652.91 | €79,874.24 | €13,534.80 (1.20x) |
| **Fold 5** (`2022-09-01 to 2023-12-01`) | €16,138.36 | €96,033.55 | €21,430.83 | €110,973.89 | €14,940.34 (1.16x) |
| **5-Fold Summary (`mean ± std`)** | **€16,070.19 ± €3,064.67** | **€67,850.89 ± €24,590.22** | **€21,209.75 ± €4,681.47** | **€79,883.94 ± €27,547.27** | **€12,033.05** |

---

## 2. Mathematical Properties vs. TrackFlow E-Commerce Seasonality

TrackFlow's consolidated monthly revenue series is governed by three structural dynamics documented in `docs/sales-forecasting/trackflow-BRIEFING.es.md`:
1. **Alternating Annual Secular Growth**: Base annual growth of $X = 6\%$ with variation $Y = 3\%$, alternating yearly between **$3\%$ and $9\%$** positive growth.
2. **Sharp Q4 Holiday Surges (November–December)**: A **+25% to +35%** revenue and shipment surge driven by Black Friday and Christmas e-commerce fulfillment.
3. **Post-Holiday Q1 Trough (February)**: A **-10% to -15%** contraction following the holiday season, while normal months fluctuate within **$\pm 5\%$** of the trend.

Because **MAE** weights all monthly residuals linearly ($\|y_i - \hat{y}_i\|$), a model that achieves near-zero error during 10 calm months ($\pm 5\%$ fluctuation) but misses the November–December Black Friday / Christmas surge by **€150,000** produces a deceptively modest MAE. In contrast, **RMSE** squares every residual before averaging ($(y_i - \hat{y}_i)^2$), amplifying large errors during the November–December peak or February transition. Across our 5 chronological validation folds, Validation RMSE (**€79,883.94 ± €27,547.27**) consistently exceeds Validation MAE (**€67,850.89 ± €24,590.22**) by **€12,033.05** precisely because RMSE exposes peak-season under-prediction spikes.

---

## 3. Asymmetric Business Cost Analysis: Overestimating vs. Underestimating Revenue

In e-commerce third-party logistics (3PL), forecast errors are **not symmetric** in either direction (overestimation vs. underestimation) or magnitude (routine small deviations vs. large peak-season misses).

### 3.1 Cost of Underestimating Sales ($\hat{y}_t < y_t$ — Capacity Shortfall Risk)

When the model **underestimates** `revenue_eur` and `shipments_processed`—especially during **November–December (+25–35% peak surge)** or high-growth ($9\%$) years:

- **Ana (Warehouse Operations — Los Angeles 60% & Zaragoza 40% Hubs)**:
  - **Understaffing & Emergency Overtime**: Warehouse picking, packing, and sorting shifts are scheduled weeks in advance. A major underestimation of ~5,356 shipments forces Ana to hire last-minute agency labor at $1.5\times–2.0\times$ overtime rates across the Los Angeles (60% volume, ~3,214 shipments) and Zaragoza (40% volume, ~2,142 shipments) fulfillment centers.
  - **Packaging Stockouts & SLA Penalties**: Running out of corrugated boxes, dunnage, and labels during Black Friday halts dispatch lines, triggering e-commerce merchant SLA penalty clauses and permanent client churn.
- **Carlos (Carrier Management)**:
  - **Spot-Market Freight Surcharges**: Carrier linehaul and last-mile capacity blocks must be contracted ahead of Q4. When actual shipment volume exceeds the forecast beyond buffer tolerances, Carlos must purchase ad-hoc spot-market trucking and air capacity at **30%–50% premium surcharges**, severely compressing TrackFlow's gross margin per shipment (`avg_revenue_per_shipment_eur`).
- **Thomas (CEO)**:
  - **Unprepared Capital & Working-Capital Strain**: Missing upside revenue surges blinds executive leadership to working-capital requirements and masks regional acceleration in the US or Spain hubs.

### 3.2 Cost of Overestimating Sales ($\hat{y}_t > y_t$ — Idle Resource & Masking Risk)

When the model **overestimates** `revenue_eur` and `shipments_processed`—particularly during the **February post-holiday dip (-10–15%)** or when transitioning from a $9\%$ growth year into a $3\%$ growth year:

- **Ana (Warehouse Operations)**:
  - **Idle Labor & Inventory Carrying Costs**: Over-scheduling warehouse shift personnel and over-ordering packaging consumables for shipments that never materialize creates direct payroll waste and ties up warehouse floor space in Los Angeles and Zaragoza.
- **Carlos (Carrier Management)**:
  - **Dead-Freight / Minimum Volume Commitment (MVC) Penalties**: Over-committing guaranteed parcel volume to carriers results in unused capacity fees and weakens Carlos's negotiating leverage in subsequent carrier rate renewals.
- **Thomas (CEO)**:
  - **False Alarms vs. Structural Anomaly Masking**: If the model fails to accurately predict the normal **-10% to -15% February seasonal dip** (overestimating February revenue), Thomas cannot distinguish a routine post-holiday e-commerce slowdown from an acute operational failure or client attrition in Los Angeles or Zaragoza.

### 3.3 Summary Matrix of Error Direction & Magnitude by Stakeholder

| Stakeholder & Hub Scope | Underestimation Impact ($\hat{y}_t < y_t$, e.g., Nov–Dec Surge Miss) | Overestimation Impact ($\hat{y}_t > y_t$, e.g., Feb Dip Miss) | Sensitivity to Large Outliers (Quadratic vs. Linear Cost) |
|---|---|---|---|
| **Ana (Warehouse Operations)**<br/>*LA (60%) & Zaragoza (40%)* | **CRITICAL**: Fulfillment bottlenecks, 1.5x–2.0x emergency overtime, packaging stockouts, merchant SLA breaches. | **MODERATE–HIGH**: Idle warehouse shift payroll, excess packaging inventory holding costs. | **Quadratic (Non-Linear)**: Small $\pm 5\%$ errors are absorbed by standard shift flex; a +25% peak miss causes warehouse gridlock. |
| **Carlos (Carrier Management)**<br/>*US & Spain Linehaul/Parcel* | **CRITICAL**: Forced purchase of spot-market freight capacity at 30%–50% peak surcharges; missed carrier cutoffs. | **HIGH**: Dead-freight penalties on unused minimum volume commitments (MVCs). | **Quadratic (Non-Linear)**: Spot carrier rates escalate non-linearly once contracted tier caps are breached. |
| **Thomas (CEO)**<br/>*Consolidated Executive Planning* | **HIGH**: Missed revenue guidance and unallocated hub expansion capital. | **CRITICAL**: Confuses normal February (-10–15%) dips with structural business contraction or regional hub outages. | **Quadratic (Non-Linear)**: Large single-month forecast failures destroy executive confidence in the dashboard before launch. |

---

## 4. Primary Decision Metric Justification: Why RMSE Over MAE

### Decision: **RMSE is Selected as TrackFlow's Primary Model Evaluation & Staging Gate Metric**

1. **Alignment with Non-Linear Logistics Cost Escalation**:
   - In TrackFlow's warehouse and carrier operations, **small monthly forecast errors ($\pm 3\%–5\%$) carry near-zero marginal penalty** because Ana's standard shift rosters and Carlos's tiered carrier contracts include routine operational buffer.
   - Conversely, **a single large forecast error ($> 10\%–15\%$) during the November–December Black Friday / Christmas peak (+25–35%) or the February trough (-10–15%) inflicts quadratic financial damage**: spot-market carrier surcharges, emergency overtime labor, SLA breach penalties, and executive misdiagnosis.
   - Because **RMSE** squares individual monthly errors prior to averaging, it penalizes a single €140,000 peak-season miss far more heavily than ten €14,000 routine monthly fluctuations—matching TrackFlow's true operational loss function.
2. **Complementary Role of MAE**:
   - **MAE** (**€67,850.89 ± €24,590.22** on validation) is retained and reported alongside RMSE as an intuitive linear baseline for Thomas and Ana ("on a typical month, the forecast deviates by €67,850.89 or ~4,549 shipments").
   - Moreover, tracking the **RMSE-to-MAE ratio** ($\text{RMSE} / \text{MAE} = 1.18\times$ across validation folds) serves as an automatic diagnostic indicator of whether model errors are evenly distributed across the calendar year ($\text{ratio} \approx 1.25\times$) or concentrated in severe seasonal outlier spikes.
