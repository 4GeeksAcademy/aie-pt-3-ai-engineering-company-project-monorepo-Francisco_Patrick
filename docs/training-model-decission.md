# Decisión de Selección Algorítmica: Random Forest vs. XGBoost para Pronóstico de Ventas

**Fecha**: 10 de noviembre de 2026  
**Proyecto**: TrackFlow Monorepo — Pipeline de Pronóstico de Ventas con Modelos de Regresión  
**Audiencia**: Thomas (Director Ejecutivo / CEO), Ana (Líder de Operaciones y Almacén), Andrés Kim (CTO)  
**Estado**: Aprobado / Implementado  

---

## 1. Resumen Ejecutivo

Para la planificación de demanda, capacidad operativa en hubs de distribución y asignación presupuestaria en TrackFlow, se evaluaron dos arquitecturas líderes de ensamble de árboles para modelar la serie temporal mensual consolidada (120 meses: 2016 a 2025): **Random Forest Regressor** y **XGBoost (Extreme Gradient Boosting)**.

Tras un análisis riguroso de trade-offs bajo las restricciones del proyecto, **se seleccionó Random Forest Regressor como el modelo principal de producción**, conservando XGBoost como benchmark comparativo. Esta decisión garantiza una robustez matemática óptima ante el tamaño reducido del dataset ($N=120$, con 96 meses de entrenamiento), proporciona un intervalo nativo de incertidumbre del 95% ($\pm 1.96\sigma$) y ofrece interpretabilidad directa para la toma de decisiones ejecutivas sin riesgo de sobreajuste.

---

## 2. Marco Comparativo y Dimensiones de Trade-Off

| Dimensión de Decisión | Random Forest Regressor | XGBoost (Gradient Boosted Trees) | Decisión Favorable |
|---|---|---|---|
| **Resiliencia ante Muestras Pequeñas ($N=96$)** | **Alta**: El ensamble paralelo con *Bootstrap Aggregation* (bagging) y selección aleatoria de variables promedia errores independientes y mitiga el sobreajuste. | **Media/Baja**: La optimización secuencial de gradiente tiende a memorizar el ruido residual en datasets pequeños ($<500$ muestras) salvo regularización extrema. | **Random Forest** |
| **Cuantificación Nativa de Incertidumbre** | **Nativa**: La varianza empírica entre las predicciones de los 100 árboles genera directamente la desviación típica $\sigma_t$ y el intervalo al 95%. | **Compleja**: Requiere entrenar tres modelos independientes para regresión por cuantiles ($\alpha=0.05, 0.50, 0.95$) o calibración conforme externa. | **Random Forest** |
| **Explicabilidad para Stakeholders** | **Excelente**: Importancia de características directa y comprensible para dirección (impacto de picos de Q4 vs. rezagos mensuales). | **Buena**: Requiere cálculo adicional de valores SHAP y árboles de decisión dependientes de la secuencia de boosting. | **Random Forest** |
| **Estabilidad de Hiperparámetros** | **Muy Alta**: Prácticamente insensible a la sintonización; con $n\_estimators=100$ el error de generalización se estabiliza. | **Baja**: Altamente sensible a la tasa de aprendizaje (`learning_rate`), profundidad (`max_depth`), submuestreo y regularización L1/L2. | **Random Forest** |
| **Tiempo de Ejecución y Determinismo** | **Inmediato**: Ejecución determinista en $<2$ segundos con semilla fija (`random_state=42`). | **Rápido**: Requiere múltiples iteraciones de validación cruzada para evitar sobreajuste. | **Random Forest** |

---

## 3. Justificación Técnica Detallada

### 3.1. Restricción del Tamaño Muestral ($N=120$) y Riesgo de Sobreajuste

La serie temporal histórica de TrackFlow comprende 10 años continuos (120 meses). Bajo la partición cronológica estricta sin fuga temporal, el conjunto de entrenamiento dispone de exactamente **96 meses** (2016–2023) y el conjunto de prueba fuera de muestra de **24 meses** (2024–2025).

En problemas de regresión con menos de 100 observaciones, los algoritmos basados en *Gradient Boosting* (como XGBoost o LightGBM) construyen árboles secuenciales donde cada nuevo estimador intenta corregir los residuos del anterior. Esta formulación es altamente eficaz en escenarios de big data, pero en datasets pequeños suele ajustar el ruido aleatorio idiosincrásico de meses particulares, produciendo varianza excesiva en el test set.

Por el contrario, Random Forest construye árboles en paralelo a partir de submuestras con reemplazo (*bootstrap*). El error de predicción del ensamble decrece a medida que se agregan árboles, garantizando que el modelo no diverge ni sobreajusta la tendencia secular o la volatilidad histórica.

### 3.2. Rango de Variabilidad e Intervalos de Confianza al 95%

Una necesidad crítica transmitida por Ana (Operaciones) es no disponer únicamente de una estimación puntual en euros, sino de un **rango de variabilidad o banda de incertidumbre** para dimensionar los turnos de almacén y las compras de material de embalaje antes de los picos de noviembre y diciembre (+25% a +35%) y las caídas de febrero (-10% a -15%).

Con Random Forest, cada uno de los 100 árboles $\hat{y}_b(x)$ emite una predicción independiente. La desviación estándar muestral entre los árboles:

$$\sigma_{\text{trees}}(x) = \sqrt{\frac{1}{B-1} \sum_{b=1}^B \left(\hat{y}_b(x) - \bar{y}(x)\right)^2}$$

Combinada con el error residual cuadrático medio intrínseco, permite trazar la envolvente de incertidumbre:

$$\text{Banda}_{95\%} = \hat{y}(x) \pm 1.96 \cdot \sigma_t$$

En XGBoost, obtener esta envolvente exigiría formular una función de pérdida *pinball* y entrenar tres modelos independientes para los percentiles 2.5%, 50% y 97.5%, triplicando la complejidad operativa y aumentando el riesgo de cruce de cuantiles (*quantile crossing*).

### 3.3. Comprensión e Interpretabilidad para Thomas y Ana

Thomas (CEO) requiere justificar ante el comité de dirección por qué el modelo proyecta un crecimiento determinado o por qué el margen de error en un trimestre específico se amplía. Random Forest permite descomponer de forma transparente las contribuciones de:
1. **Factores estacionales y calendario**: Indicadores binarios de Black Friday/Navidad (`is_peak_season`) y desaceleración de febrero (`is_february_dip`).
2. **Anclas autorregresivas**: Rezago de 12 meses (`lag_12`), que ancla la base interanual del mismo mes del año anterior.
3. **Dinámica de corto plazo**: Rezago inmediato (`lag_1`) y medias móviles trimestrales (`rolling_mean_3`), que capturan la inercia reciente del negocio.

---

## 4. Estrategia de Evaluación Multimétrica Aprobada

Para validar que el modelo no sólo minimiza el error cuadrático medio sino que es estructuralmente sano, se implementan cuatro dimensiones complementarias:

1. **Mean Squared Error (MSE en EUR² y % de Facturación Media)**:
   - Cuantifica la magnitud absoluta del error promedio en euros. Se normaliza dividiendo la raíz cuadrada (RMSE) entre la facturación mensual promedio (~€1.3M) para presentar a dirección una métrica intuitiva en porcentaje ($<5\%$).
2. **Population Stability Index (PSI)**:
   - Valida que la distribución de ventas de los 24 meses de test no haya sufrido un desplazamiento estructural respecto a los 8 años de entrenamiento ($\text{PSI} < 0.10 \implies \text{Estable}$).
3. **Coeficiente Gini de Discriminación Estacional**:
   - Mide la capacidad del modelo para ordenar correctamente los meses de alta demanda frente a los de baja demanda ($\text{Gini} > 0.60$), garantizando que noviembre nunca sea pronosticado por debajo de febrero.
4. **Test K2 de Normalidad Residual (D'Agostino-Pearson)**:
   - Contrasta si los errores de predicción $e_t = y_t - \hat{y}_t$ siguen una distribución gaussiana ($p > 0.05$), confirmando la ausencia de sesgos no lineales o anomalías sistemáticas desatendidas.

---

## 5. Conclusión y Recomendación

La adopción de **Random Forest Regressor** en `scripts/train_sales_forecast.py` y el paquete `data/pipelines/sales_forecast/` cumple con la totalidad de los requisitos técnicos, operativos y de gobernanza de la Constitución de TrackFlow. Proporciona una solución determinista, reproducible, explicable y robusta, lista para la toma de decisiones estratégicas.

