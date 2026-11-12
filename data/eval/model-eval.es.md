# Justificación de Costos de Negocio y Métricas de Error: MAE vs. RMSE

**Funcionalidad**: `025-regression-model-evaluation`  
**Variable objetivo**: `revenue_eur` (`market == "consolidated"` en `data/raw/trackflow_sales.csv`)  
**Impulsores de volumen operativo**: `shipments_processed` y `avg_revenue_per_shipment_eur` (~14,91 €/envío entre **Los Ángeles [EE. UU., 60 % del volumen]** y **Zaragoza [España, 40 % del volumen]**)  
**Métrica principal de decisión seleccionada**: **RMSE (Error Cuadrático Medio / Root Mean Squared Error)** (acompañada de **MAE** como métrica secundaria lineal para interpretación ejecutiva)  

---

## 1. Resumen Empírico de Error de Entrenamiento y Validación (Validación Cruzada Temporal de 5 Pliegues)

Evaluado estrictamente a través de **5 pliegues cronológicos en expansión** (*expanding chronological folds*) dentro de la partición de entrenamiento de 8 años (`2016-01-01` a `2023-12-01`, 96 meses, manteniendo intacto el conjunto de prueba *hold-out* de 2024–2025), el modelo base `RandomForestRegressor(n_estimators=100, random_state=42)` alcanza las siguientes distribuciones de error:

| Métrica | Conjunto de entrenamiento (`media ± desv. est.`) | Conjunto de validación (`media ± desv. est.`) | Error equivalente en volumen de envíos (`media val.`) | Ponderación matemática |
|---|---|---|---|---|
| **MAE (Error Absoluto Medio)** | **16.070,19 € ± 3.064,67 €** | **67.850,89 € ± 24.590,22 €** | ~**4.549 envíos/mes** | Penalización lineal: $\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} \|y_i - \hat{y}_i\|$ |
| **RMSE (Raíz del Error Cuadrático Medio)** | **21.209,75 € ± 4.681,47 €** | **79.883,94 € ± 27.547,27 €** | ~**5.356 envíos/mes** (3.214 LA / 2.142 Zaragoza) | Penalización cuadrática de valores atípicos: $\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (y_i - \hat{y}_i)^2}$ |

### Comparación de MAE vs. RMSE por pliegue en ventanas en expansión

| Pliegue cronológico (Periodo de validación) | MAE Entren. (EUR) | MAE Val. (EUR) | RMSE Entren. (EUR) | RMSE Val. (EUR) | Dispersión de atípicos: RMSE Val. − MAE Val. |
|---|---|---|---|---|---|
| **Pliegue 1** (`2017-05-01 a 2018-08-01`) | 21.295,84 € | 42.022,88 € | 29.232,83 € | 52.882,05 € | 10.859,17 € (1,26x) |
| **Pliegue 2** (`2018-09-01 a 2019-12-01`) | 13.675,59 € | 89.277,94 € | 18.883,79 € | 103.645,98 € | 14.368,04 € (1,16x) |
| **Pliegue 3** (`2020-01-01 a 2021-04-01`) | 14.220,67 € | 45.580,65 € | 17.848,41 € | 52.043,55 € | 6.462,90 € (1,14x) |
| **Pliegue 4** (`2021-05-01 a 2022-08-01`) | 15.020,51 € | 66.339,44 € | 18.652,91 € | 79.874,24 € | 13.534,80 € (1,20x) |
| **Pliegue 5** (`2022-09-01 a 2023-12-01`) | 16.138,36 € | 96.033,55 € | 21.430,83 € | 110.973,89 € | 14.940,34 € (1,16x) |
| **Resumen de 5 pliegues (`media ± desv. est.`)** | **16.070,19 € ± 3.064,67 €** | **67.850,89 € ± 24.590,22 €** | **21.209,75 € ± 4.681,47 €** | **79.883,94 € ± 27.547,27 €** | **12.033,05 €** |

---

## 2. Propiedades Matemáticas vs. Estacionalidad del Comercio Electrónico en TrackFlow

La serie mensual de ingresos consolidados de TrackFlow se rige por tres dinámicas estructurales documentadas en `docs/sales-forecasting/trackflow-BRIEFING.es.md`:
1. **Crecimiento secular anual alterno**: Crecimiento anual base de $X = 6\%$ con una variación $Y = 3\%$, alternando anualmente entre un crecimiento positivo del **$3\%$ y del $9\%$**.
2. **Fuertes repuntes festivos en el cuarto trimestre (noviembre–diciembre)**: Un aumento del **+25 % al +35 %** en ingresos y envíos impulsado por la logística de comercio electrónico del Black Friday y Navidad.
3. **Caída posterior a las fiestas en el primer trimestre (febrero)**: Una contracción del **-10 % al -15 %** tras la temporada navideña, mientras que los meses normales fluctúan dentro de un margen de **$\pm 5\%$** respecto a la tendencia.

Dado que el **MAE** pondera todos los residuos mensuales de forma lineal ($\|y_i - \hat{y}_i\|$), un modelo que logre un error cercano a cero durante 10 meses tranquilos (fluctuación de $\pm 5\%$), pero que falle por **150.000 €** en el repunte de Black Friday y Navidad de noviembre–diciembre, arroja un MAE engañosamente modesto. En cambio, el **RMSE** eleva al cuadrado cada residuo antes de promediarlos ($(y_i - \hat{y}_i)^2$), amplificando los errores graves durante el pico de noviembre–diciembre o la transición de febrero. A lo largo de nuestros 5 pliegues cronológicos de validación, el RMSE de validación (**79.883,94 € ± 27.547,27 €**) supera sistemáticamente al MAE de validación (**67.850,89 € ± 24.590,22 €**) en **12.033,05 €** precisamente porque el RMSE deja al descubierto los picos de subestimación en temporada alta.

---

## 3. Análisis Asimétrico de Costos de Negocio: Sobreestimar vs. Subestimar los Ingresos

En la logística de terceros (3PL) para comercio electrónico, los errores de pronóstico **no son simétricos** ni en dirección (sobreestimación frente a subestimación) ni en magnitud (pequeñas desviaciones rutinarias frente a grandes fallos en temporada alta).

### 3.1 Costo de subestimar las ventas ($\hat{y}_t < y_t$ — Riesgo de déficit de capacidad)

Cuando el modelo **subestima** `revenue_eur` y `shipments_processed` —especialmente durante el **repunte máximo de noviembre–diciembre (+25–35 %)** o en años de alto crecimiento ($9\%$):

- **Ana (Operaciones de Almacén — Centros de Los Ángeles 60 % y Zaragoza 40 %)**:
  - **Falta de personal y horas extra de emergencia**: Los turnos de *picking*, empaquetado y clasificación en almacén se programan con semanas de antelación. Una subestimación importante de ~5.356 envíos obliga a Ana a contratar personal externo de última hora con tarifas de horas extra de $1,5\times–2,0\times$ en los centros de cumplimiento de Los Ángeles (60 % del volumen, ~3.214 envíos) y Zaragoza (40 % del volumen, ~2.142 envíos).
  - **Rotura de stock de embalaje y penalizaciones por SLA**: Quedarse sin cajas de cartón corrugado, material de relleno y etiquetas durante el Black Friday paraliza las líneas de despacho, activando cláusulas de penalización por incumplimiento de acuerdos de nivel de servicio (SLA) con los comercios y provocando la pérdida definitiva de clientes.
- **Carlos (Gestión de Transportistas)**:
  - **Recargos de flete en el mercado *spot***: Los bloques de capacidad de transporte troncal (*linehaul*) y última milla deben contratarse antes del cuarto trimestre. Cuando el volumen real de envíos supera el pronóstico más allá de los márgenes de tolerancia, Carlos debe adquirir capacidad terrestre y aérea *ad-hoc* en el mercado *spot* con **recargos de entre el 30 % y el 50 %**, comprimiendo gravemente el margen bruto por envío de TrackFlow (`avg_revenue_per_shipment_eur`).
- **Thomas (CEO)**:
  - **Capital no previsto y tensión en el capital de trabajo**: Pasar por alto los repuntes al alza de ingresos impide que la dirección ejecutiva anticipe las necesidades de capital de trabajo y oculta la aceleración regional en los centros de EE. UU. o España.

### 3.2 Costo de sobreestimar las ventas ($\hat{y}_t > y_t$ — Riesgo de recursos ociosos y enmascaramiento)

Cuando el modelo **sobreestima** `revenue_eur` y `shipments_processed` —en particular durante la **caída posnavideña de febrero (-10–15 %)** o al pasar de un año de crecimiento del $9\%$ a uno del $3\%$:

- **Ana (Operaciones de Almacén)**:
  - **Mano de obra ociosa y costos de mantenimiento de inventario**: Programar turnos de personal en exceso y sobreabastecerse de consumibles de embalaje para envíos que nunca se materializan genera un desperdicio directo en nómina y ocupa espacio valioso en los almacenes de Los Ángeles y Zaragoza.
- **Carlos (Gestión de Transportistas)**:
  - **Penalizaciones por falso flete / Compromiso de Volumen Mínimo (MVC)**: Comprometer un volumen garantizado de paquetería superior al real ante los transportistas conlleva tarifas por capacidad no utilizada y debilita el poder de negociación de Carlos en las siguientes renovaciones de tarifas.
- **Thomas (CEO)**:
  - **Falsas alarmas vs. enmascaramiento de anomalías estructurales**: Si el modelo no logra predecir con precisión la **caída estacional habitual de febrero del -10 % al -15 %** (sobreestimando los ingresos de febrero), Thomas no podrá distinguir entre una desaceleración posnavideña normal del comercio electrónico y un fallo operativo grave o pérdida de clientes en Los Ángeles o Zaragoza.

### 3.3 Matriz resumen de dirección y magnitud del error por parte interesada

| Parte interesada y alcance operativo | Impacto de la subestimación ($\hat{y}_t < y_t$, ej. fallo en el pico de nov.–dic.) | Impacto de la sobreestimación ($\hat{y}_t > y_t$, ej. fallo en la caída de feb.) | Sensibilidad a grandes valores atípicos (Costo cuadrático vs. lineal) |
|---|---|---|---|
| **Ana (Operaciones de Almacén)**<br/>*LA (60 %) y Zaragoza (40 %)* | **CRÍTICO**: Cuellos de botella en preparación de pedidos, horas extra de emergencia a 1,5x–2,0x, rotura de stock de embalaje, incumplimiento de SLA con comercios. | **MODERADO–ALTO**: Nómina de turnos de almacén ociosos, costos de almacenamiento por exceso de inventario de embalaje. | **Cuadrática (No lineal)**: Los errores pequeños de $\pm 5\%$ se absorben con la flexibilidad estándar de turnos; un fallo del +25 % en temporada alta colapsa el almacén. |
| **Carlos (Gestión de Transportistas)**<br/>*Transporte troncal y paquetería en EE. UU. y España* | **CRÍTICO**: Compra forzosa de capacidad de transporte en el mercado *spot* con recargos del 30 %–50 %; pérdida de horarios de corte de transportistas. | **ALTO**: Penalizaciones por falso flete sobre compromisos de volumen mínimo (MVC) no utilizados. | **Cuadrática (No lineal)**: Las tarifas *spot* de los transportistas escalan de forma no lineal una vez superados los límites de los tramos contratados. |
| **Thomas (CEO)**<br/>*Planificación ejecutiva consolidada* | **ALTO**: Desviación respecto a las previsiones de ingresos y falta de asignación de capital para expansión de centros. | **CRÍTICO**: Confunde las caídas normales de febrero (-10–15 %) con una contracción estructural del negocio o interrupciones en centros regionales. | **Cuadrática (No lineal)**: Los grandes fallos de pronóstico en un solo mes destruyen la confianza ejecutiva en el panel de control antes de su lanzamiento. |

---

## 4. Justificación de la Métrica Principal de Decisión: Por Qué RMSE Frente a MAE

### Decisión: **Se selecciona el RMSE como métrica principal de evaluación del modelo y criterio de validación para pase a producción (*Staging Gate*) de TrackFlow**

1. **Alineación con la escalada no lineal de los costos logísticos**:
   - En las operaciones de almacén y transporte de TrackFlow, **los errores mensuales pequeños en el pronóstico ($\pm 3\%–5\%$) conllevan una penalización marginal casi nula**, ya que la planificación estándar de turnos de Ana y los contratos escalonados de transportistas de Carlos incluyen un margen operativo habitual.
   - Por el contrario, **un único error grave en el pronóstico ($> 10\%–15\%$) durante el pico de Black Friday y Navidad de noviembre–diciembre (+25–35 %) o la caída de febrero (-10–15 %) provoca un daño financiero cuadrático**: recargos de transportistas en el mercado *spot*, mano de obra de emergencia con horas extra, penalizaciones por incumplimiento de SLA y diagnósticos ejecutivos erróneos.
   - Dado que el **RMSE** eleva al cuadrado los errores mensuales individuales antes de promediarlos, penaliza un único desvío de 140.000 € en temporada alta mucho más severamente que diez fluctuaciones mensuales rutinarias de 14.000 €, reflejando fielmente la verdadera función de pérdida operativa de TrackFlow.
2. **Rol complementario del MAE**:
   - El **MAE** (**67.850,89 € ± 24.590,22 €** en validación) se mantiene y reporta junto con el RMSE como una referencia lineal intuitiva para Thomas y Ana («en un mes típico, el pronóstico se desvía en 67.850,89 € o ~4.549 envíos»).
   - Además, el seguimiento de la **relación RMSE/MAE** ($\text{RMSE} / \text{MAE} = 1,18\times$ en los pliegues de validación) sirve como un indicador diagnóstico automático para determinar si los errores del modelo se distribuyen uniformemente a lo largo del año calendario ($\text{relación} \approx 1,25\times$) o si se concentran en picos estacionales atípicos graves.