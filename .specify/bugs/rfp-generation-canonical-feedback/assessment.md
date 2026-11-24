# Bug Assessment: RFP Generation Parallel Execution, Canonical BRIEFING Grounding & Feedback Application

- **Slug**: rfp-generation-canonical-feedback
- **Created**: 2026-11-23T17:08:00+01:00
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> Hay tres bloqueos ahora mismo. Los departamentos se generan en serie: uno bloquea al otro; solo los evaluadores corren en paralelo. Los borradores inventan datos contra el BRIEFING: SLA 99,2/98,5/99,0 % en vez del 90 %; almacenamiento 16,50 EUR o 18 USD por pallet/SKU en vez de 16 EUR/18 USD por m³; descuentos 5/10/15 % sin aprobación de Miguel Torres. El evaluador los aprueba (solo busca un 9x %). El generador real ignora el feedback: la iteración 2 es idéntica salvo una nota. Usa los valores canónicos, marca lo no publicado como pendiente y aplica el feedback

## Symptom

Al ejecutar el pipeline de generación de propuestas RFP (Hito 9 Parte 2), se presentan tres bloqueos críticos operativos y de consistencia:

1. **Serialización bloqueante entre departamentos**:
   En `data/pipelines/rfp_response_generation/pipeline.py:276-289`, el bucle que procesa los departamentos activos (`warehouse`, `lastmile`, `reverse`) se ejecuta en estricta serie (`for dept_id in active_departments:`). Si un departamento requiere múltiples iteraciones de generación-evaluación, bloquea por completo la ejecución de los demás departamentos. La única concurrencia implementada está confinada a la evaluación interna multidimensional de un único borrador dentro de `evaluator.py`.

2. **Alucinación de datos frente a las fuentes canónicas del BRIEFING y aprobación laxa del evaluador**:
   - **SLA de entrega / operaciones**: `FALLBACK_BRIEFING_STANDARDS` y las plantillas de generadores hardcodean SLAs del 99,2% (Warehouse), 98,5% (Last Mile) y 99,0% (Reverse Logistics), contradiciendo el SLA canónico del **90%** contractualmente establecido en `docs/company-knowledge-base/trackflow-sla-delivery.es.md` y `docs/agentic-workflows/trackflow-BRIEFING.es.md` (§5).
   - **Tarifas de almacenamiento**: Los generadores cotizan 16,50 EUR o 18 USD por pallet o por SKU (`pallet_monthly`, `sku_pick_pack`), cuando `docs/company-knowledge-base/trackflow-storage-pricing.es.md` estipula claramente que TrackFlow cobra almacenamiento según **volumen ocupado en metros cúbicos ($m^3$)**: **16 EUR por $m^3$ al mes en Zaragoza** y **18 USD por $m^3$ al mes en Los Ángeles**.
   - **Descuentos por volumen sin aprobación de Miguel Torres**: Se emite automáticamente una tabla de descuentos de 5%, 10% y 15% sin reflejar la gobernanza comercial de TrackFlow, donde cualquier tarifa o descuento preferencial (especialmente > 50 $m^3$) requiere aprobación obligatoria y explícita de **Miguel Torres (Director Comercial)**.
   - **Falsa validación en el evaluador**: En `data/pipelines/rfp_response_generation/compliance_rules.py:153`, `validate_rule_sla` utiliza una expresión regular laxa `r"\b9\d(?:[.,]\d+)?\s*%"` que valida cualquier porcentaje en los 90s (como 99,2% o 98,5%), aprobando borradores no conformes sin detectar el desvío del 90% contractual. Del mismo modo, `validate_rule_discount_tiers` solo revisa la presencia visual de una tabla de descuentos sin comprobar la restricción de gobernanza de Miguel Torres.

3. **Incapacidad del generador para aplicar el feedback en revisiones**:
   En `data/pipelines/rfp_intake/rfp_generator_agents.py:298-306, 404-411, 508-515`, cuando `feedback_for_generator` se pasa en la iteración 2, los generadores reales ignoran el contenido del feedback. Simplemente re-emiten exactamente el mismo texto anterior y le adjuntan al final un párrafo genérico ("`### 5. Revision Note (Attempt X)`"). No corrigen los datos impugnados, ni marcan los parámetros no publicados como pendientes, imposibilitando la convergencia genuina del bucle generador-evaluador.

4. **Error adicional de importación**:
   Debido a la reciente reubicación de `rfp_generator_agents.py` a `data/pipelines/rfp_intake/`, `pipeline.py` y los tests unitarios bajo `tests/pipelines/` contienen imports rotos hacia `application.agent.rfp_generator_agents`, causando `ModuleNotFoundError`.

## Reproduction

1. **Inspeccionar serialización en `pipeline.py`**:
   Abrir `data/pipelines/rfp_response_generation/pipeline.py:276-289`. Constatar que `for dept_id in active_departments:` ejecuta `run_department_loop` secuencialmente en el hilo principal para cada departamento en vez de paralelizar los bucles por departamento.
2. **Inspeccionar valores en generadores y reglas de cumplimiento**:
   Abrir `data/pipelines/rfp_intake/rfp_generator_agents.py:22-84, 101-113, 265, 270`. Observar que:
   - Los SLAs asignados son `99.2%`, `98.5%`, `99.0%` en vez del 90% canónico.
   - Las tarifas de almacenamiento se definen como `16.50 EUR` y `$18.00 USD` por pallet, y se cobra por SKU, en contradicción con `trackflow-storage-pricing.es.md` (16 EUR / 18 USD por $m^3$).
   - `build_volume_discount_table` ofrece descuentos del 5%, 10% y 15% sin estipular la aprobación mandataria de Miguel Torres.
3. **Inspeccionar evaluador en `compliance_rules.py`**:
   Revisar `validate_rule_sla` en `data/pipelines/rfp_response_generation/compliance_rules.py:153`. La condición `re.search(r"\b9\d(?:[.,]\d+)?\s*%", text)` valida como exitoso cualquier porcentaje que comience por 9 (99,2%, 98,5%, etc.).
4. **Inspeccionar aplicación de feedback en `rfp_generator_agents.py`**:
   Revisar los métodos `generate(...)` en `WarehouseGeneratorAgent`, `LastMileGeneratorAgent` y `ReverseLogisticsGeneratorAgent`. Observar que la sección de revisión solo añade texto estático y nunca modifica el cuerpo del borrador con base en `feedback_for_generator`.
5. **Ejecutar suite de tests con Python del entorno virtual**:
   Ejecutar `services/api/.venv/Scripts/pytest.exe tests/pipelines/test_rfp_response_generation.py`. Se observa `ModuleNotFoundError: No module named 'application.agent'` y tests desalineados que esperan los valores incorrectos.

## Suspected Code Paths

- `data/pipelines/rfp_response_generation/pipeline.py:28, 275-289` — Orquestación serial de bucles departamentales e importación obsoleta de generadores.
- `data/pipelines/rfp_intake/rfp_generator_agents.py:22-84, 101-113, 254-307, 364-412, 466-516` — Definición de `FALLBACK_BRIEFING_STANDARDS`, `build_volume_discount_table` e implementación estática de revisiones en los tres generadores sin procesar feedback.
- `data/pipelines/rfp_response_generation/compliance_rules.py:48-95, 142-161, 219-249` — Reglas de cumplimiento `RULE-SLA` (expresión regular laxa que acepta cualquier 9x%) y `RULE-DISCOUNT-TIERS` (falta de chequeo de gobernanza con Miguel Torres).
- `data/pipelines/rfp_response_generation/evaluator.py:38-160` — Asignación de keywords y evaluación de relevancia/legibilidad/cumplimiento.
- `tests/pipelines/test_compliance_rules.py:40, 57` — Aserciones desactualizadas que validan 16,50 EUR y 98,5% SLA.
- `tests/pipelines/test_rfp_generators.py:55, 88` — Aserciones desactualizadas esperando 99,2% y 98,5%.
- `tests/pipelines/test_rfp_feedback_loop.py:27-58` — Mock artificial de autocorrección en lugar de probar la corrección real de los generadores.
- `tests/pipelines/test_rfp_iteration_cap.py`, `tests/pipelines/test_rfp_handoff_packaging.py`, `tests/pipelines/test_rfp_evaluators.py` — Dependencias directas sobre la ejecución del pipeline y aserciones de valores canónicos.

## Root Cause Hypothesis

Durante la implementación inicial del Hito 9 Parte 2:
1. **Ejecución secuencial**: El pipeline se estructuró con un bucle `for` lineal sobre `active_departments`, asumiendo erróneamente que la concurrencia a nivel de dimensiones del evaluador (`ThreadPoolExecutor` dentro de `evaluator.py`) satisfacía los requisitos de paralelismo entre departamentos.
2. **Desconexión con el BRIEFING canónico**: Se introdujeron valores arbitrarios en `FALLBACK_BRIEFING_STANDARDS` (SLAs ficticios de 98,5% - 99,2% y tarifas por pallet de 16,50 EUR / SKU pick & pack) en lugar de respetar las políticas oficiales de TrackFlow documentadas en `docs/company-knowledge-base/` (SLA contractual de 90%, almacenamiento estricto por metro cúbico a 16 EUR Zaragoza / 18 USD Los Ángeles, y descuentos que requieren la aprobación obligatoria de Miguel Torres).
3. **Validador laxo**: Para que los tests iniciales pasaran, la función `validate_rule_sla` se codificó con `r"\b9\d"` tolerando cualquier 9x%, enmascarando los desvíos respecto al 90% contractual.
4. **Generador ciego a feedback**: El flujo iterativo se implementó como un placeholder cosmético donde la revisión solo concatena una nota de intento sin reescribir ni ajustar las secciones impugnadas ni marcar ítems como pendientes.
5. **Ruta de módulo tras refactor**: Al mover los módulos de agentes a `data/pipelines/rfp_intake/`, quedaron enlaces rotos a `application.agent`.

Confianza: Alta.

## Proposed Remediation

**Preferred**:

1. **Paralelizar la generación entre departamentos**:
   En `RFPResponseGenerationPipeline.execute_from_handoff`, sustituir el bucle secuencial por ejecución concurrente de `self.run_department_loop` usando `concurrent.futures.ThreadPoolExecutor` (con `max_workers=len(active_departments)`). Garantizar que la persistencia en base de datos (`update_department_section_draft`) gestione sesiones aisladas o bloqueos seguros para evitar colisiones de sesión en SQLAlchemy/SQLModel.

2. **Alinear a los valores canónicos del BRIEFING**:
   - **SLA**: Establecer como estándar canónico el **90%** (o 90,0%) en todos los departamentos según `trackflow-sla-delivery.es.md` y `trackflow-BRIEFING.es.md` (§5).
   - **Almacenamiento**: Ajustar tarifas a **16 EUR por $m^3$ al mes** (Zaragoza / ES) y **18 USD por $m^3$ al mes** (Los Ángeles / US). Eliminar cobros inventados por pallet/SKU en la tarifa base, y si la RFP no especifica volumen o dimensiones, marcar explícitamente los costos y capacidades adicionales como *"Pendiente de confirmación según volumen en $m^3$"*.
   - **Descuentos por volumen y Gobernanza**: En `build_volume_discount_table`, reflejar que cualquier descuento por volumen (5%, 10%, 15% o volúmenes > 50 $m^3$) está expresamente condicionado a la aprobación de **Miguel Torres (Director Comercial)**, rotulando los tramos no formalizados como *"Pendiente de aprobación comercial por Miguel Torres"*.

3. **Endurecer los evaluadores de cumplimiento**:
   - En `validate_rule_sla`, verificar estrictamente que el texto comprometa el SLA contractual del **90%** (o rechazar menciones desalineadas).
   - En `validate_rule_discount_tiers`, asegurar que las menciones a descuentos respeten la gobernanza de Miguel Torres y no comprometan rebajas unilaterales.

4. **Hacer que los generadores consuman y apliquen el feedback activamente**:
   - En `WarehouseGeneratorAgent`, `LastMileGeneratorAgent` y `ReverseLogisticsGeneratorAgent`, implementar una lógica de revisión reactiva al `feedback_for_generator`: si el feedback señala desalineación en moneda, falta de keywords, tiempo de retorno < 48h, o ausencia de la mención al 90% SLA o a Miguel Torres, el generador debe corregir dinámicamente el contenido del borrador en la iteración $N > 1$, además de incorporar las notas de revisión correspondientes.
   - Marcar cualquier aspecto operativo no publicado en el briefing canónico (como tarifas específicas de manipulación especial no tarifadas) como *"Pendiente"*.

5. **Corregir imports y actualizar la suite de tests**:
   - Actualizar los imports en `pipeline.py` y `tests/pipelines/*.py` para apuntar a `data.pipelines.rfp_intake.rfp_generator_agents`.
   - Actualizar las aserciones en `test_compliance_rules.py`, `test_rfp_generators.py` y tests de pipeline para validar el 90% SLA, tarifas en $m^3$ (16 EUR / 18 USD), gobernanza de Miguel Torres y la aplicación efectiva de feedback en la iteración 2.

**Alternatives**:
- *Orquestar con asyncio en lugar de ThreadPoolExecutor*: Implementar las llamadas a generadores y evaluadores como corrutinas asíncronas con `asyncio.gather`. Sin embargo, dado que `textstat` y los parsers de compliance son síncronos/CPU-bound y el repositorio SQLModel actual es síncrono, `ThreadPoolExecutor` ofrece una integración directa y de menor riesgo.

**Files likely to change**:
- `data/pipelines/rfp_response_generation/pipeline.py`
- `data/pipelines/rfp_intake/rfp_generator_agents.py`
- `data/pipelines/rfp_response_generation/compliance_rules.py`
- `data/pipelines/rfp_response_generation/evaluator.py`
- `tests/pipelines/test_compliance_rules.py`
- `tests/pipelines/test_rfp_generators.py`
- `tests/pipelines/test_rfp_feedback_loop.py`
- `tests/pipelines/test_rfp_response_generation.py`
- `tests/pipelines/test_rfp_iteration_cap.py`

**Tests to add or update**:
- Actualizar `test_warehouse_generator_modaviva_spain_eur_draft`: verificar 90% SLA, 16 EUR por $m^3$, mención a Miguel Torres para descuentos y marcas de pendiente.
- Actualizar `test_lastmile_generator_luna_cosmetics_us_usd_draft`: verificar 90% SLA, 18 USD por $m^3$ o tarifas finales de transporte, y Miguel Torres.
- Actualizar `test_validate_rule_sla_requires_percentage_commitment`: asegurar que valida 90% SLA canónico.
- Crear / actualizar test en `test_rfp_feedback_loop.py`: validar que un generador real (sin mock auxiliar) toma el feedback de un intento fallido y reescribe sustancialmente el borrador para subsanar los puntos señalados.
- Test de concurrencia: verificar que los departamentos corren en paralelo en `execute_from_handoff`.

## Risks & Considerations

- **Thread safety en la sesión de base de datos**: Si múltiples hilos llaman concurrentemente a `self.repository.update_department_section_draft` compartiendo la misma sesión de SQLModel/SQLAlchemy, pueden ocurrir condiciones de carrera o conflictos de transacción (`PendingRollbackError` o accesos concurrentes no soportados). Se debe asegurar una sesión por hilo o sincronización con `threading.Lock` para las operaciones del repositorio.
- **Impacto en tests preexistentes**: Varios tests de regresión verificaban explícitamente los valores erróneos (`99.2%`, `98.5%`, `16.50 EUR`); deben actualizarse de manera consistente en una única pasada para mantener la integridad de la suite.

## Open Questions

- Ninguna. Las directivas canónicas de `trackflow-storage-pricing.es.md` (16 EUR / 18 USD por $m^3$, aprobación obligatoria de Miguel Torres para descuentos) y `trackflow-sla-delivery.es.md` (90% SLA contractual) están claramente definidas en la documentación oficial.
