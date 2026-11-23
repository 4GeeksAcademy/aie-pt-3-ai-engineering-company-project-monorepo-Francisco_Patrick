# Bug Fix: RFP Generation Parallel Execution, Canonical BRIEFING Grounding & Feedback Application

- **Slug**: rfp-generation-canonical-feedback
- **Fixed**: 2026-11-23T17:23:00+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Paralelizó la generación de propuestas departamentales en `execute_from_handoff` mediante `ThreadPoolExecutor` con sincronización de repositorio, alineó todos los generadores y estándares de fallback al SLA canónico del 90%, tarifas en $m^3$ (16 EUR Zaragoza / 18 USD Los Ángeles) y gobernanza de Miguel Torres, endureció los evaluadores de cumplimiento y dotó a los generadores de reactividad activa ante el feedback del evaluador en revisiones.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `data/pipelines/rfp_response_generation/pipeline.py` | modified | Concurrencia entre departamentos con `ThreadPoolExecutor`, bloqueo de hilo para persistencia segura en repo y corrección de imports a `data.pipelines.rfp_intake.rfp_generator_agents`. |
| `data/pipelines/rfp_intake/rfp_generator_agents.py` | modified | Canónico 90% SLA, almacenamiento por $m^3$ (16 EUR / 18 USD), gobernanza comercial de Miguel Torres en tabla de descuentos, marcas 'Pendiente' y aplicación activa de feedback en revisión. |
| `data/pipelines/rfp_response_generation/compliance_rules.py` | modified | Validación estricta del 90% SLA en `validate_rule_sla` y gobernanza mandataria de Miguel Torres en `validate_rule_discount_tiers`. |
| `services/api/presentation/api/v1/rfp.py` | modified | Resolución de marcadores de conflicto de merge e imports actualizados hacia `data.pipelines.rfp_intake`. |
| `services/api/tests/unit/agent/test_rfp_generator_agents.py` | modified | Imports corregidos y aserción del 90% SLA canónico en fallback de knowledge retrieval. |
| `services/api/tests/integration/test_rfp_generation_api.py` | modified | Import corregido hacia `data.pipelines.rfp_intake.rfp_intake_pipeline`. |
| `tests/pipelines/test_compliance_rules.py` | modified | Aserciones actualizadas para 90% SLA canónico y aprobación de Miguel Torres en tabla de descuentos. |
| `tests/pipelines/test_rfp_compliance_failures.py` | modified | Fixtures alineados al SLA canónico y gobernanza para aislar la falla en `RULE-RETURNS-TIME`. |
| `tests/pipelines/test_rfp_evaluators.py` | modified | Import corregido a `data.pipelines.rfp_intake.rfp_generator_agents`. |
| `tests/pipelines/test_rfp_generators.py` | modified | Aserciones de 90% SLA, 16.00 EUR por $m^3$, Miguel Torres y marcas de 'Pendiente'. |
| `tests/pipelines/test_rfp_iteration_cap.py` | modified | Imports corregidos y aislamiento de falla por turnaround de devoluciones con gobernanza y 90% SLA. |
| `tests/pipelines/test_rfp_feedback_loop.py` | modified | Imports corregidos y adición del test de reactividad activa a feedback `test_real_generators_actively_consume_feedback_on_revision`. |
| `tests/pipelines/test_rfp_response_generation.py` | modified | Adición de test de concurrencia `test_pipeline_executes_departments_concurrently`. |

## Diff Highlights (optional)

```python
# Concurrencia departamental en execute_from_handoff:
if len(active_departments) > 1:
    with ThreadPoolExecutor(max_workers=len(active_departments)) as executor:
        future_to_dept = {
            executor.submit(self.run_department_loop, ...): dept_id
            for dept_id in active_departments
        }
        for future in future_to_dept:
            outcomes[future_to_dept[future]] = future.result()

# Validación estricta del 90% SLA contractual:
has_canonical_90 = bool(re.search(r"\b90(?:[.,]0+)?\s*%", text))
if not (has_sla_keyword and has_canonical_90):
    return False, BRIEFING_COMPLIANCE_RULES["RULE-SLA"].failure_message
```

## Tests Added or Updated

- `tests/pipelines/test_compliance_rules.py::test_validate_rule_sla_requires_percentage_commitment` — Exige y valida el 90% SLA canónico, rechazando desvíos no canónicos como 98.5%.
- `tests/pipelines/test_compliance_rules.py::test_validate_rule_discount_tiers_requires_table_or_tiers` — Exige gobernanza explícita de Miguel Torres en la tabla de descuentos.
- `tests/pipelines/test_rfp_generators.py::test_warehouse_generator_modaviva_spain_eur_draft` — Verifica 90% SLA, 16.00 EUR por $m^3$, Miguel Torres y marcas de pendiente.
- `tests/pipelines/test_rfp_generators.py::test_lastmile_generator_luna_cosmetics_us_usd_draft` — Verifica 90% SLA, tarifas USD y gobernanza de Miguel Torres.
- `tests/pipelines/test_rfp_generators.py::test_reverse_generator_enforces_48h_minimum_turnaround` — Verifica 90% SLA, >= 48h turnaround y Miguel Torres.
- `tests/pipelines/test_rfp_feedback_loop.py::test_real_generators_actively_consume_feedback_on_revision` — Verifica que los generadores reales aplican feedback en iteración 2 corrigiendo el borrador.
- `tests/pipelines/test_rfp_response_generation.py::test_pipeline_executes_departments_concurrently` — Verifica ejecución paralela de departamentos en hilos independientes.

## Local Verification

- Commands run:
  - `services/api/.venv/Scripts/pytest.exe tests/pipelines/test_compliance_rules.py tests/pipelines/test_rfp_compliance_failures.py tests/pipelines/test_rfp_evaluators.py tests/pipelines/test_rfp_feedback_loop.py tests/pipelines/test_rfp_generators.py tests/pipelines/test_rfp_handoff_packaging.py tests/pipelines/test_rfp_iteration_cap.py tests/pipelines/test_rfp_response_generation.py` → 40 passed in 13.31s.
  - `services/api/.venv/Scripts/pytest.exe services/api/tests/unit/agent/test_rfp_generator_agents.py services/api/tests/integration/test_rfp_generation_api.py` → 6 passed in 1.38s.
- Manual checks: Verificación de concurrencia de hilos (`len(executed_threads) >= 2`) y ausencia de referencias erróneas de moneda cruzada en `policy_note`.

## Deviations from Assessment

Ninguna. La remediación se aplicó conforme a lo establecido en `assessment.md`.

## Follow-ups

- Ejecutar la verificación formal con `/speckit-bug-test slug=rfp-generation-canonical-feedback`.
