# Bug Assessment: RFP Approval Completion Traces, Rejection Lifecycle & Canonical Values

- **Slug**: rfp-approval-trace-rejection
- **Created**: 2026-11-23T17:39:30+01:00
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> El trace solo cubre los nodos de la rama: el final_synthesis_node descarta su trace y el arbitration_node no está cableado (se llama la función); esos nodos no quedan registrados con input/output. Un reject finaliza la rama pero deja el ticket en esperando_aprobación para siempre, sin documento ni reanudación (409); debe llevar a un estado terminal o permitir reabrir, y la espera debe ser solo para HITL pendiente. El documento final hereda los valores erróneos de la Parte 2 (99,2 % SLA, 16,50 EUR/pallet); corrige la Parte 2 antes de cerrar el hito.

## Symptom

1. **Pérdida de trazabilidad de ejecución (Execution Traces)**: La lista `execution_trace` sólo contiene entradas de los nodos internos de las ramas (`prepare_branch_review`, `human_approval_checkpoint`, `finalize_branch_approval`/`rejection`). `final_synthesis_node` calcula su traza pero la canalización la descarta en el gate de síntesis, y `arbitration_node` nunca es invocado como nodo del grafo (se llama directamente a la función de negocio subyacente `evaluate_and_arbitrate_conflicts`), dejando ambos nodos sin registrar sus snapshots de `input` y `output`.
2. **Bloqueo zombi por rechazo de departamento (Rejection Dead-End)**: Cuando un responsable de departamento emite una decisión `reject`, la rama finaliza en `END` y borra su `snapshot.next`. Sin embargo, `_evaluate_ticket_completion_gate()` mantiene indefinidamente el ticket en `esperando_aprobación` a pesar de que no restan pausas HITL activas en esa rama. Cualquier intento posterior de interactuar o reanudar esa rama lanza una excepción `BranchNotInterruptedError` (HTTP 409 Conflict), impidiendo tanto la finalización del ticket como su reapertura o descarte formal.
3. **Contaminación de valores no canónicos de Parte 2**: A pesar de la unificación del BRIEFING canónico en Parte 2 (SLA contractual del 90% y cobro de almacenaje en $m^3$ a 16 EUR / 18 USD), diversos fixtures de test y mocks en Parte 3 (`test_rfp_approval_interrupts.py`, `test_rfp_arbitration.py`, `test_rfp_final_synthesis.py`) continúan inyectando valores obsoletos (`99.2% SLA`, `16.50 EUR/pallet`), los cuales son heredados y compilados textualmente en el `FinalDocument` generado.

## Reproduction

1. **Verificar omisión de `final_synthesis_node` y `arbitration_node` en traces**:
   - Ejecutar la reanudación con aprobación de todos los departamentos en `RFPApprovalCompletionPipeline.resume_department_approval()`.
   - Inspeccionar el diccionario retornado en la clave `execution_trace`: contiene únicamente los pasos del subgrafo de la rama que acaba de reanudarse.
   - Observar que en `data/pipelines/rfp_approval_completion/pipeline.py:600`, se invoca `evaluate_and_arbitrate_conflicts()` omitiendo `arbitration_node()`, y en la línea 632, la traza resultante de `final_synthesis_node(synth_state)` no es propagada ni consolidada en el estado o repositorio.
2. **Verificar estado zombi tras rechazo (`reject`)**:
   - Iniciar la fase de aprobación con `start_approval_phase()`.
   - Reanudar una rama con payload `{"decision": "reject", "approver": "Ana Whitfield", "feedback": "Rechazado por falta de viabilidad"}`.
   - La rama transiciona a `finalize_branch_rejection` y llega a `END` (`snapshot.next` es nulo).
   - Comprobar el estado retornado del ticket: permanece en `esperando_aprobación` (`waiting_for_approval`).
   - Invocar nuevamente `resume_department_approval()` sobre el mismo departamento: se lanza `BranchNotInterruptedError` con mensaje `"Department branch 'warehouse' ... is not currently paused in an interrupt"` (HTTP 409). El ticket queda huérfano para siempre sin documento ni resolución.
3. **Verificar herencia de valores erróneos en el documento final**:
   - Ejecutar `tests/pipelines/test_rfp_final_synthesis.py` o inspeccionar `test_rfp_arbitration.py:78,200` y `test_rfp_approval_interrupts.py:96`.
   - Comprobar que los borradores de entrada contienen `99.2% SLA` y `16.50 EUR per pallet`.
   - Observar que `synthesize_final_document()` incrusta dichos textos directamente en `FinalDocument.sections[dept]["approved_content"]`, consolidando datos contrarios al BRIEFING oficial.

## Suspected Code Paths

- `data/pipelines/rfp_approval_completion/pipeline.py:377-384, 599-605`: Invocación directa de `evaluate_and_arbitrate_conflicts` en lugar de `arbitration_node(state)`, saltándose el decorador `@traced_node("arbitration_node")`.
- `data/pipelines/rfp_approval_completion/pipeline.py:623-633`: Llamada a `final_synthesis_node()`, tras la cual se descarta `synth_state.get("execution_trace")`.
- `data/pipelines/rfp_approval_completion/pipeline.py:539`: `resume_department_approval()` devuelve únicamente `branch_state.get("execution_trace")`, perdiendo las trazas globales de arbitraje y síntesis final.
- `data/pipelines/rfp_approval_completion/pipeline.py:596-598`: `_evaluate_ticket_completion_gate()` retorna `TicketStatus.WAITING_FOR_APPROVAL.value` por defecto cuando `can_synthesize_final_document` es falso, incluso si hay ramas en estado `rejected` sin pausas HITL pendientes.
- `data/pipelines/rfp_approval_completion/pipeline.py:476-487`: Bloqueo con 409 (`BranchNotInterruptedError`) al intentar reabrir o rectificar una rama finalizada en `rejected`.
- `data/pipelines/rfp_approval_completion/pipeline.py:36`: Import obsoleto `from application.agent.rfp_generator_agents import ...` no actualizado tras la reubicación a `data/pipelines/rfp_intake/`.
- `tests/pipelines/test_rfp_approval_interrupts.py:11,96`: Import roto de `application.agent` y borrador con `99.2% SLA`.
- `tests/pipelines/test_rfp_arbitration.py:12-13,78,200`: Imports rotos y textos con `16.50 EUR per pallet` y `99.2% SLA`.
- `tests/pipelines/test_rfp_final_synthesis.py:12,101,210,326`: Imports rotos y secciones con `16.50 EUR` y `99.2% SLA`.
- `tests/pipelines/test_rfp_e2e_complete.py:16-18`: Imports rotos hacia `application.agent.*`.
- `uis/backoffice/__tests__/DepartmentApprovalPanel.test.tsx:43`: Fixture de prueba con `16.50 EUR per pallet`.

## Root Cause Hypothesis

Existen tres causas raíz independientes:
1. **Falta de integración de nodos trazados**: `arbitration_node` y `final_synthesis_node` fueron implementados y anotados con `@traced_node`, pero el orquestador `pipeline.py` los eludió: llamó directamente a la función de lógica interna para arbitraje y no capturó ni propagó la traza devuelta por `final_synthesis_node`. Tampoco se unifican las trazas de nivel ticket con las de nivel rama en el momento de la reanudación final. (Confianza: alta).
2. **Incompletitud en la máquina de estados de aprobación**: El ciclo de vida contempló la transición a `terminado` (100% aprobadas) y `needs_human_review` (escalación por exceso de revisiones), pero omitió la gestión terminal o de reapertura cuando ocurre un `rejected`. Al terminar la rama en `END`, la condición de guardia del checkpointer la considera no interrumpible (409) mientras que el ticket permanece estancado en `esperando_aprobación`, violando el principio de que `esperando_aprobación` solo debe regir mientras existan pausas HITL pendientes. (Confianza: alta).
3. **Arrastre de fixtures y mocks no canónicos de Parte 2**: Al migrar y probar la Parte 3, se copiaron fixtures de prueba generados con la versión previa de Parte 2 (que inventaba tarifas de 16,50 EUR/pallet y 99,2% SLA en lugar de los 16 EUR/$m^3$ y 90% SLA canónicos). Dado que `synthesis.py` compila fielmente el contenido aprobado sin alteración de datos operativos, estos valores erróneos acaban plasmados en el documento final. (Confianza: alta).

## Proposed Remediation

**Preferred**:
1. **Cablear `arbitration_node` y preservar trazas en `pipeline.py`**:
   - Sustituir las llamadas directas a `evaluate_and_arbitrate_conflicts` en `start_approval_phase` y `_evaluate_ticket_completion_gate` por invocaciones a `arbitration_node(state)`.
   - Propagar `execution_trace` en el estado de retorno de `_evaluate_ticket_completion_gate()`, consolidando las trazas de `arbitration_node` y `final_synthesis_node` junto con las trazas de la rama correspondiente en `resume_department_approval()`.
   - Si se dispone de repositorio, persistir o anexar estas trazas al ticket.
2. **Gestionar el ciclo de vida ante `rejected` y corregir estados de espera**:
   - En `_evaluate_ticket_completion_gate`: si alguna rama activa registra `rejected`, evaluar si el ticket debe transicionar a un estado terminal adecuado (por ejemplo, `descartado` si la propuesta queda inviable, o escalación a `needs_human_review` bajo la dirección comercial de Miguel Torres, de acuerdo con la especificación de gobernanza de TrackFlow), asegurando que el ticket nunca permanezca en `esperando_aprobación` si no hay pausas HITL activas pendientes.
   - En `resume_department_approval`: permitir la reapertura de una rama previamente rechazada si se suministra una acción explícita de reapertura o reinicio de borrador, evitando el rechazo ciego con 409 cuando el ticket requiera subsanación comercial.
3. **Sanear fixtures, mocks e imports en Parte 3 con valores canónicos del BRIEFING**:
   - Actualizar los imports en `pipeline.py` y en toda la suite de tests (`test_rfp_approval_interrupts.py`, `test_rfp_arbitration.py`, `test_rfp_final_synthesis.py`, `test_rfp_e2e_complete.py`) de `application.agent.*` a `data.pipelines.rfp_intake.*`.
   - Reemplazar en todos los fixtures y aserciones de prueba los valores no canónicos (`99.2% SLA` -> `90% SLA`, `16.50 EUR per pallet` -> `16.00 EUR por m³` o tarifas canónicas de Zaragoza).
   - Validar que el `FinalDocument` resultante refleje exclusivamente el SLA del 90% y almacenaje en $m^3$.

**Alternatives**:
- *Alternativa de estado terminal*: En lugar de marcar el ticket como `descartado` directamente tras un rechazo departamental, derivarlo siempre a `needs_human_review` asignado a Miguel Torres (Director Comercial) para arbitraje comercial superior. Esto concuerda con la regla del briefing que establece que un rechazo departamental puede ser renegociado o arbitrar una alternativa comercial antes de descartar formalmente al cliente.

**Files likely to change**:
- `data/pipelines/rfp_approval_completion/pipeline.py`
- `data/pipelines/rfp_approval_completion/arbitration.py`
- `data/pipelines/rfp_approval_completion/synthesis.py`
- `services/api/domain/rfp/entities.py` (si se requiere método helper de transición en `Ticket`)
- `tests/pipelines/test_rfp_approval_interrupts.py`
- `tests/pipelines/test_rfp_arbitration.py`
- `tests/pipelines/test_rfp_final_synthesis.py`
- `tests/pipelines/test_rfp_e2e_complete.py`
- `uis/backoffice/__tests__/DepartmentApprovalPanel.test.tsx`

**Tests to add or update**:
- Test unitario que verifique que `execution_trace` contiene explícitamente entradas para `arbitration_node` y `final_synthesis_node` con sus respectivos `input_state` y `output_state`.
- Test de ciclo de vida que verifique que cuando una rama es rechazada (`decision="reject"`):
  - El ticket transiciona a un estado terminal/escalado (`descartado` o `needs_human_review`).
  - El ticket NO permanece en `esperando_aprobación`.
  - Se valida el comportamiento ante intentos de reanudación o reapertura comercial.
- Test de síntesis final verificando que `FinalDocument.sections` contenga los SLAs canónicos (90%) y unidades de almacenamiento conformes al BRIEFING ($m^3$).

## Risks & Considerations

- **Compatibilidad con checkpointer de LangGraph**: Reabrir una rama que ya alcanzó `END` requiere o bien un nuevo `thread_id` / checkpoint de iteración, o bien transicionar a través de una rama de arbitraje/revisión en lugar de transicionar directamente a `END`.
- **Contrato de API REST**: Los clientes frontend (`uis/backoffice`) esperan valores canónicos en `ticket_status`. Al evitar el estancamiento en `esperando_aprobación`, la interfaz debe reaccionar adecuadamente a estados como `descartado` o `needs_human_review`.
- **Integridad de la suite de regresión**: Actualizar los imports rotos de `application.agent` a `data.pipelines.rfp_intake` desbloqueará la ejecución de la suite completa de tests de Parte 3.

## Open Questions

- *Ninguna bloqueante*: La política de gobernanza del briefing establece con claridad que las discrepancias no resueltas o bloqueos por rechazo recaen sobre el Director Comercial (Miguel Torres) o derivan en el descarte del ticket, y los valores del briefing son 90% SLA y 16 EUR / 18 USD por $m^3$.
