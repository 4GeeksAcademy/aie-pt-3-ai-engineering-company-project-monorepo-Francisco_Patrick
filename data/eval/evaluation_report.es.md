# Informe de Evaluación Técnica y Diagnóstico de Ajuste del Modelo

**Modelo Bajo Evaluación**: `RandomForestRegressor(n_estimators=100, random_state=42)`  
**Conjunto de Datos**: `data/raw/trackflow_sales.csv` (`market == "consolidated"`, variable objetivo `revenue_eur`)  
**Partición de Evaluación**: Ventana Histórica de Entrenamiento de 8 Años (`2016-01-01` a `2023-12-01`, 96 meses)  
**Partición de Prueba Reservada (Hold-Out)**: Ventana de Prueba No Vista de 2 Años (`2024-01-01` a `2025-12-01`, 24 meses — **Estrictamente Aislada / Intacta**)  
**Estrategia de Validación Cruzada**: División Cronológica de Ventana Expansiva de 5 Pliegues (Cero Fuga de Datos Futuros / Lookahead Leakage)  

---

## 1. Diagnóstico Ejecutivo y Veredicto de Preparación para Preproducción (Staging)

| Dimensión de Evaluación | Resultado / Veredicto |
|---|---|
| **Clasificación Explícita de Ajuste del Modelo** | **`overfitting`** |
| **Métrica Principal de Decisión** | **RMSE** (Raíz del Error Cuadrático Medio en `revenue_eur`) |
| **MAE de Entrenamiento en Validación Cruzada (`media ± desv. est.`)** | **16.070,19 € ± 3.064,67 €** |
| **MAE de Validación en Validación Cruzada (`media ± desv. est.`)** | **67.850,89 € ± 24.590,22 €** |
| **RMSE de Entrenamiento en Validación Cruzada (`media ± desv. est.`)** | **21.209,75 € ± 4.681,47 €** |
| **RMSE de Validación en Validación Cruzada (`media ± desv. est.`)** | **79.883,94 € ± 27.547,27 €** |
| **Relación de Brecha RMSE Validación-Entrenamiento** | **3,77x** (NRMSE de Validación: **8,19%** de los ingresos medios) |
| **Recomendación de Promoción a Preproducción (Staging)** | **`HOLD_REQUIRES_REMEDIATION`** |

---

## 2. Resultados de Validación Cruzada Temporal Multi-Pliegue (`media ± desv. est.`)

Para verificar si el flujo de pronóstico base generaliza a lo largo de los ciclos anuales alternos de alto crecimiento ($9\%$) y bajo crecimiento ($3\%$) de TrackFlow sin filtrar datos futuros, el conjunto de datos de entrenamiento de 96 meses (`2016-01-01` a `2023-12-01`) se dividió en **5 pliegues cronológicos expansivos**. Dentro de cada pliegue $k \in \{1 \dots 5\}$:
1. Las características de rezago causal (`lag_1`, `lag_2`, `lag_3`, `lag_12`), las estadísticas de ventana móvil (`rolling_mean_3`, `rolling_mean_6`, `rolling_std_3`) y los indicadores de calendario (`month_num`, `quarter`, `is_peak_season`, `is_february_dip`, `trend_index`) se calcularon estrictamente sobre la porción histórica visible hasta el límite del pliegue.
2. `StandardScaler` se ajustó **exclusivamente** sobre las filas de entrenamiento históricas del pliegue (`X_fold_train`) y se aplicó a `X_fold_val`.

### 2.1 Desglose por Pliegue

| Pliegue | Ventana de Entrenamiento ($N_{\text{train}}$) | Ventana de Validación ($N_{\text{val}}$) | MAE Entrenamiento (EUR) | MAE Validación (EUR) | RMSE Entrenamiento (EUR) | RMSE Validación (EUR) | Ingresos Medios de Validación (EUR) |
|---|---|---|---|---|---|---|---|
| **Pliegue 1** | `2016-01-01 a 2017-04-01` (16m) | `2017-05-01 a 2018-08-01` (16m) | 21.295,84 € | 42.022,88 € | 29.232,83 € | 52.882,05 € | 852.387,62 € |
| **Pliegue 2** | `2016-01-01 a 2018-08-01` (32m) | `2018-09-01 a 2019-12-01` (16m) | 13.675,59 € | 89.277,94 € | 18.883,79 € | 103.645,98 € | 956.013,67 € |
| **Pliegue 3** | `2016-01-01 a 2019-12-01` (48m) | `2020-01-01 a 2021-04-01` (16m) | 14.220,67 € | 45.580,65 € | 17.848,41 € | 52.043,55 € | 981.004,45 € |
| **Pliegue 4** | `2016-01-01 a 2021-04-01` (64m) | `2021-05-01 a 2022-08-01` (16m) | 15.020,51 € | 66.339,44 € | 18.652,91 € | 79.874,24 € | 1.069.331,54 € |
| **Pliegue 5** | `2016-01-01 a 2022-08-01` (80m) | `2022-09-01 a 2023-12-01` (16m) | 16.138,36 € | 96.033,55 € | 21.430,83 € | 110.973,89 € | 1.202.304,47 € |
| **Agregado (`media ± desv. est.`)** | **16 → 80 meses** | **16 meses / pliegue** | **16.070,19 € ± 3.064,67 €** | **67.850,89 € ± 24.590,22 €** | **21.209,75 € ± 4.681,47 €** | **79.883,94 € ± 27.547,27 €** | — |

---

## 3. Análisis de la Curva de Aprendizaje y Evidencia Empírica de `overfitting`

El artefacto de la curva de aprendizaje guardado en `data/eval/learning_curve.png` traza el Error de Entrenamiento dentro de la muestra y el Error de Validación fuera de la muestra (tanto MAE como RMSE) a través de tamaños crecientes de muestras de entrenamiento cronológicas ($N_{\text{train}} = 16, 32, 48, 64, 80$ meses).

### 3.1 Tabla de Trayectoria de la Curva de Aprendizaje

| Tamaño de Muestra de Entrenamiento ($N_{\text{train}}$) | MAE Entrenamiento (EUR) | MAE Validación (EUR) | RMSE Entrenamiento (EUR) | RMSE Validación (EUR) | Brecha de Generalización RMSE (EUR) | Relación RMSE Val / Entren. |
|---|---|---|---|---|---|---|
| **16 meses** | 21.295,84 € | 42.022,88 € | 29.232,83 € | 52.882,05 € | 23.649,22 € | 1,81x |
| **32 meses** | 13.675,59 € | 89.277,94 € | 18.883,79 € | 103.645,98 € | 84.762,19 € | 5,49x |
| **48 meses** | 14.220,67 € | 45.580,65 € | 17.848,41 € | 52.043,55 € | 34.195,14 € | 2,92x |
| **64 meses** | 15.020,51 € | 66.339,44 € | 18.652,91 € | 79.874,24 € | 61.221,33 € | 4,28x |
| **80 meses** | 16.138,36 € | 96.033,55 € | 21.430,83 € | 110.973,89 € | 89.543,06 € | 5,18x |

### 3.2 Justificación Cuantitativa de la Clasificación de Ajuste del Modelo (`overfitting`)

A lo largo de los 5 pliegues cronológicos expansivos (tamaños de entrenamiento N = 16, 32, 48, 64, 80 meses), el RMSE de entrenamiento dentro de la muestra promedia 21.209,75 € ± 4.681,47 € (2,17% de los ingresos medios) y el MAE de entrenamiento promedia 16.070,19 € ± 3.064,67 €, mientras que el RMSE de validación fuera de la muestra salta a 79.883,94 € ± 27.547,27 € (8,19% de los ingresos medios) y el MAE de validación alcanza los 67.850,89 € ± 24.590,22 €. Esto arroja una relación de RMSE de validación frente a entrenamiento de 3,77x (relación de MAE de 4,22x). En la curva de aprendizaje, a medida que el historial de entrenamiento se expande de N=16 (RMSE de entrenamiento 29.232,83 € frente a RMSE de validación 52.882,05 €, brecha de 1,81x) a N=80 (RMSE de entrenamiento 21.430,83 € frente a RMSE de validación 110.973,89 €, brecha de 5,18x), el error de entrenamiento dentro de la muestra permanece deprimido cerca de ~18.000 €–29.000 €, mientras que el error de validación fuera de la muestra se amplía hasta los 110.973,89 € a medida que crecen los ingresos nominales a lo largo de los años, dejando una brecha de generalización sin cerrar de 89.543,06 € (5,18x).

Observaciones diagnósticas clave de la curva de aprendizaje (`data/eval/learning_curve.png`):
- **Error de Entrenamiento Dentro de la Muestra Persistentemente Bajo**: En los 5 tamaños de muestra cronológicos, el RMSE de entrenamiento permanece estrechamente acotado entre **29.232,83 €** y **21.430,83 €** (`21.209,75 € ± 4.681,47 €`), lo que demuestra que el Random Forest sin restricciones memoriza las observaciones históricas de entrenamiento.
- **Amplia Brecha de Generalización Entre Pliegues**: El RMSE de validación fuera de la muestra promedia **79.883,94 € ± 27.547,27 €**, más de **3,77 veces** superior al RMSE de entrenamiento. Incluso en la ventana de entrenamiento más grande ($N = 80$ meses en el Pliegue 5), el RMSE de validación (**110.973,89 €**) sigue siendo **5,18 veces** superior al RMSE de entrenamiento (**21.430,83 €**).
- **Régimen de Crecimiento Entre Pliegues y Varianza Estacional**: A lo largo de los 5 pliegues, el RMSE de validación fluctúa con una desviación estándar de **27.547,27 €** (oscilando entre **52.043,55 €** en el Pliegue 3 y **110.973,89 €** en el Pliegue 5). Los pliegues cuyas ventanas de validación abarcan repuntes festivos del cuarto trimestre (Q4) de alto crecimiento ($9\%$) (Pliegue 2 en `2018-09`–`2019-12` con **103.645,98 €** y Pliegue 5 en `2022-09`–`2023-12` con **110.973,89 €**) sufren un severo sesgo de límite de función escalonada porque las hojas de los árboles de decisión no pueden predecir por encima del máximo histórico de entrenamiento, mientras que el RMSE de entrenamiento se mantiene artificialmente bajo (**21.430,83 €**) debido a la memorización de árboles sin restricciones.

---

## 4. Diagnóstico de Causa Raíz y Acción Correctiva Concreta

### 4.1 Causa Raíz Diagnosticada

Dos mecanismos acoplados en el modelo base RandomForestRegressor(n_estimators=100, max_depth=None, min_samples_leaf=1) impulsan este patrón de sobreajuste (overfitting) en la serie de 96 meses: (1) Profundidad de Árbol Sin Restricciones y Hojas de Muestra Única — con los valores predeterminados max_depth=None y min_samples_leaf=1 en ventanas mensuales compactas (16 a 80 observaciones), los árboles de decisión individuales particionan el espacio de características hasta que las hojas terminales aíslan meses históricos individuales, memorizando el ruido dentro de la muestra (fluctuaciones mensuales de ±5%) y reduciendo el RMSE de entrenamiento hasta ~3% de los ingresos; y (2) Techo de Extrapolación de Función Escalonada en el Crecimiento Secular No Estacionario — los ingresos consolidados de TrackFlow se capitalizan a un ritmo de 6% ± 3% anual (alternando años de crecimiento del 3% y 9%), lo que significa que cada pliegue de validación cronológico opera en un régimen nominal en EUR más alto que su ventana de entrenamiento anterior, y los ensambles de árboles no pueden extrapolar tendencias lineales más allá del valor máximo y_train observado durante el entrenamiento (provocando una subestimación sistemática de los picos durante los repuntes de noviembre-diciembre de +25–35%).

### 4.2 Acción Correctiva Concreta y Alineada con la Causa Raíz

Implementar una remediación en dos partes antes de promover el modelo al entorno de preproducción (staging): (1) Regularización Estructural de Árboles — restringir la complejidad del árbol estableciendo max_depth=4, min_samples_leaf=2 y min_samples_split=4 (o max_features='sqrt') en RandomForestRegressor para que las hojas terminales promedien a través de múltiples ciclos estacionales en lugar de memorizar meses individuales; y (2) Eliminación de Tendencia Lineal Causal (Detrending) — ajustar una línea base de tendencia lineal causal (Ridge/OLS sobre trend_index ajustado estrictamente dentro de la ventana de entrenamiento de cada pliegue) o transformar la variable objetivo en ratios relativos interanuales (y_t / lag_12) antes de ajustar el Random Forest sobre los residuos estacionales estacionarios, eliminando el techo de extrapolación de función escalonada sobre el crecimiento anual compuesto de los ingresos del 3%–9%.

| Eje de Remediación | Configuración Base | Remediación Prescrita | Impacto Esperado en la Curva de Aprendizaje |
|---|---|---|---|
| **1. Regularización de Profundidad de Árbol y Hojas** | `max_depth=None`, `min_samples_leaf=1`, `min_samples_split=2` | Establecer `max_depth=4`, `min_samples_leaf=2`, `min_samples_split=4` en `RandomForestRegressor` | Eleva moderadamente el RMSE de entrenamiento dentro de la muestra mientras reduce la varianza del RMSE de validación fuera de la muestra entre pliegues, comprimiendo la brecha de generalización de `3,77x`. |
| **2. Extrapolación del Crecimiento Secular** | Variable objetivo `revenue_eur` sin procesar predicha directamente por hojas de árbol de función escalonada | Ajustar una línea base de tendencia lineal causal (`Ridge` / `LinearRegression` sobre `trend_index` ajustado estrictamente en `X_fold_train`) y entrenar el Random Forest sobre los residuos estacionales sin tendencia $r_t = y_t - \hat{y}_{\text{trend}, t}$ | Elimina la subestimación sistemática cuando los pliegues de validación entran en regímenes nominales en EUR más altos impulsados por la tendencia de crecimiento anual compuesto del $6\% \pm 3\%$. |

---

## 5. Recomendación de Promoción a Preproducción (Staging)

**Veredicto**: **`HOLD_REQUIRES_REMEDIATION`**

Si bien la partición cronológica del flujo de datos, la ingeniería de características causales y el aislamiento de `StandardScaler` por pliegue superan el 100% de las auditorías de fuga de datos, promover directamente a preproducción (staging) el modelo base `RandomForestRegressor` sin regularizar y sin eliminación de tendencia expondría las operaciones de TrackFlow (Ana en Operaciones de Almacén y Carlos en Gestión de Transportistas) a un RMSE de validación de **79.883,94 € ± 27.547,27 €** (**8,19%** de los ingresos medios), concentrado principalmente en los meses pico del cuarto trimestre (Q4) donde las funciones escalonadas de los árboles limitan los pronósticos de ingresos a los máximos históricos. Ingeniería debe aplicar la **regularización de profundidad de árbol (`max_depth=4, min_samples_leaf=2`) + eliminación de tendencia lineal causal** prescritas y volver a ejecutar `scripts/evaluate_sales_forecast.py` para confirmar la convergencia de la brecha antes de la promoción a preproducción.