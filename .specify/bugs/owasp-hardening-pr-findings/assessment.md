# Bug Assessment: OWASP Hardening PR Findings & Pre-Merge Remediation

- **Slug**: owasp-hardening-pr-findings
- **Created**: 2026-11-25
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

Revisión por Acceptance Criterion (AC 1–7) para el PR de endurecimiento de seguridad y auditoría OWASP Top 10 (`specs/036-owasp-audit-hardening`):

> **Hallazgos y puntos a corregir antes de mergear a `main`:**
> 1. **Cableado en runtime de `validate_tool_call_authorization` y `AgentActionPoliciesService` (`services/api`):**
>    En el diff, `validate_tool_call_authorization` (`agent_guardrails.py`) y `AgentActionPoliciesService` (`agent_action_policies.py`) están implementados y probados en tests unitarios (`test_agent_guardrails_authorization.py`, `test_agent_action_policies.py`), pero no se observa dónde los invocan las tools reales (`ticket_tool_node`, `inventory_tool_node` o los endpoints/servicios de devoluciones y carriers).
> 2. **Archivo de remediación `services/api/core/exceptions.py` ausente en el diff:**
>    Tanto `tasks.md` (`T032`), `backend_audit.md` (`SEC-BK-009`) como `critical_remediation_proof.md` (§2.2) indican que se refactorizó `services/api/core/exceptions.py` para sanear los errores 500, pero no aparece modificado en el diff (ya existía previamente en `main`).
> 3. **Endpoints HITL `/actions/review` sin autenticación/autorización (`services/api/presentation/api/v1/agent.py:1130-1175`):**
>    `GET /actions/review` y `POST /actions/review/{request_id}` no exigen `Depends(get_current_user)` ni validación de rol de supervisor, permitiendo que cualquier cliente anónimo liste o apruebe acciones pendientes de revisión humana. Además, `POST /actions/review/{request_id}` usa `decision_req: Any = Body(...)` en lugar del esquema fuertemente tipado `HumanApprovalDecisionRequest`, permitiendo suplantar `reviewer_id` en el body.
> 4. **Falso positivo en `infra/host/verify_hardening.sh`:**
>    Las comprobaciones usan `if grep ... /etc/ssh/sshd_config || grep ... infra/host/sshd_config.hardened` y `elif grep ... infra/host/ufw_setup.sh`. Si se ejecuta en un servidor sin endurecer donde exista el repositorio clonado, el script devolverá `PASS` leyendo la plantilla local del repo en lugar del estado real del sistema.
> 5. **Alcance mezclado en la PR (`035` + `036`):**
>    El diff incluye tanto el bugfix de WebSocket (`035-websocket-streaming-chat`) como la auditoría OWASP (`036-owasp-audit-hardening`), además de un archivo binario/caché de build (`uis/backoffice/tsconfig.tsbuildinfo`) que debe excluirse o revertirse.

## Symptom

Al auditar la rama `feature/owasp-top10-audit`:
1. Los endpoints administrativos de revisión humana `/actions/review` y `/actions/review/{request_id}` son accesibles públicamente sin token JWT ni autorización de rol, permitiendo la toma de decisiones por actores no autenticados y la suplantación de `reviewer_id`.
2. Las políticas de autorización de llamadas a herramientas (`validate_tool_call_authorization`) y los umbrales de acción agéntica (`AgentActionPoliciesService`) no están cableados en la ejecución de tools de los agentes en runtime (`ticket_tool_node`, `inventory_tool_node`), por lo que las peticiones reales eluden estos controles.
3. El script de verificación de hardening de host (`infra/host/verify_hardening.sh`) produce falsos positivos en entornos no configurados al evaluar las plantillas del repositorio como fallback.
4. El archivo binario de compilación `uis/backoffice/tsconfig.tsbuildinfo` y artefactos de la especificación 035 están presentes en el diff de la PR.

## Reproduction

1. **Vulnerabilidad HITL no autenticado**:
   - Iniciar la API FastAPI: `uvicorn main:app`.
   - Realizar petición HTTP sin cabecera `Authorization`: `GET /api/v1/agent/actions/review`.
   - *Resultado observado*: Devuelve HTTP 200 con la cola de revisiones sin validar autenticación.
   - Realizar petición HTTP sin cabecera `Authorization`: `POST /api/v1/agent/actions/review/{request_id}` con body `{"reviewer_id": "attacker", "approved": true}`.
   - *Resultado observado*: Aprueba la acción y asigna el revisor sin autenticar.

2. **Herramientas de agente eludiendo validación de autorización en runtime**:
   - Inspeccionar `services/api/application/services/support_agent_service.py` en los nodos de ejecución de herramientas (`ticket_tool_node` y `inventory_tool_node`).
   - *Resultado observado*: Invocan directamente la lógica de datos sin pasar por `validate_tool_call_authorization`.

3. **Falso positivo de verificación de host**:
   - Ejecutar `bash infra/host/verify_hardening.sh` en una máquina con `/etc/ssh/sshd_config` con `PermitRootLogin yes` pero teniendo la carpeta `infra/host/sshd_config.hardened`.
   - *Resultado observado*: Imprime `PASS` debido a la condición `|| grep ... infra/host/sshd_config.hardened`.

4. **Inconsistencias en diff / git status**:
   - Ejecutar `git status --porcelain uis/backoffice/tsconfig.tsbuildinfo` y `git diff origin/main services/api/core/exceptions.py`.
   - *Resultado observado*: `tsconfig.tsbuildinfo` aparece modificado; `core/exceptions.py` no tiene diff con respecto a `origin/main` porque ya estaba previamente implementado en `main`.

## Suspected Code Paths

- `services/api/presentation/api/v1/agent.py:1130-1195` — Endpoints `/actions/review` carecen de `Depends(get_current_user)` / `RoleChecker` y usan `decision_req: Any = Body(...)`.
- `services/api/presentation/schemas/security_audit.py:126-150` — `HumanApprovalDecisionRequest` está definido pero no se utiliza como schema de entrada en `POST /actions/review/{request_id}`.
- `services/api/application/services/support_agent_service.py:500-530` — `ticket_tool_node` y `inventory_tool_node` no invocan `validate_tool_call_authorization` antes de interactuar con repositorios.
- `infra/host/verify_hardening.sh:16, 24, 32, 43` — Fallback condicional con `|| grep ... infra/host/...` en lugar de validar estrictamente el estado del sistema operativo anfitrión.
- `uis/backoffice/tsconfig.tsbuildinfo` — Artefacto binario de caché TS incluido en el control de versiones.
- `docs/cybersecurity-analysis/` y `specs/036-owasp-audit-hardening/` — Documentación y evidencias que referencian `services/api/core/exceptions.py` como remediación de este PR cuando ya existía en la base.

## Root Cause Hypothesis

Durante la implementación de la especificación 036 (`specs/036-owasp-audit-hardening`), los módulos de control de seguridad agéntica (`agent_guardrails.py`, `agent_action_policies.py`) y las rutas de revisión HITL fueron desarrollados de manera modular y validados con tests unitarios aislados, pero se omitió:
1. La inyección de dependencias de autenticación (`get_current_user`, `require_supervisor_role`) y el tipado Pydantic en los nuevos endpoints de `agent.py`.
2. El middleware/interceptor en los nodos de LangGraph de `support_agent_service.py` para invocar `validate_tool_call_authorization` previo a la ejecución de cada tool.
3. Una verificación estricta orientada a producción en `verify_hardening.sh`, que fue diseñada originalmente como prueba de concepto que leía los archivos locales del repositorio en caso de no estar en un sistema Linux con SSH instalado.

Confianza: Alta.

## Proposed Remediation

**Preferred**:
1. **Asegurar Endpoints HITL en `presentation/api/v1/agent.py`**:
   - Agregar dependencia de autenticación `current_user: AuthenticatedUser = Depends(get_current_user)` a `GET /actions/review` y `POST /actions/review/{request_id}`.
   - Restringir el acceso a roles autorizados (supervisor/operaciones).
   - Reemplazar `decision_req: Any = Body(...)` por `decision_req: HumanApprovalDecisionRequest = Body(...)`.
   - Establecer `reviewer_id = current_user.email` (o `username`/`id`), impidiendo que el cliente suplante la identidad del revisor en el body.
2. **Cablear la autorización de tools en `support_agent_service.py`**:
   - Integrar la llamada a `validate_tool_call_authorization` dentro del pipeline de ejecución de tools en `support_agent_service.py` antes de despachar a `ticket_tool_node` o `inventory_tool_node`. Si la validación falla (resultado con `action="block"`), retornar inmediatamente el mensaje de denegación sin ejecutar la herramienta.
3. **Corregir `infra/host/verify_hardening.sh`**:
   - Eliminar las comprobaciones secundarias contra plantillas locales del repo (`|| grep ... infra/host/...`).
   - Evaluar exclusivamente los archivos de configuración y binarios del host (`/etc/ssh/sshd_config`, `ufw status`).
   - Proporcionar flag explicativo (e.g. `--template-check` o modo offline) solo si se desea verificar sintaxis de plantillas en CI.
4. **Limpieza del diff y clarificación de `core/exceptions.py`**:
   - Revertir o ignorar `uis/backoffice/tsconfig.tsbuildinfo` (`git checkout uis/backoffice/tsconfig.tsbuildinfo`).
   - Aclarar en la documentación de auditoría (`critical_remediation_proof.md` y `backend_audit.md`) que la remediación en `services/api/core/exceptions.py` se validó mediante el nuevo test `test_error_handling_sanitization.py` contra la implementación preexistente en la base.

**Alternatives**:
- En lugar de modificar directamente `support_agent_service.py`, implementar un tool decorator `@enforce_tool_authorization` en `agent_guardrails.py` que envuelva cualquier función de herramienta registrada en LangGraph.

**Files likely to change**:
- `services/api/presentation/api/v1/agent.py`
- `services/api/application/services/support_agent_service.py`
- `infra/host/verify_hardening.sh`
- `specs/036-owasp-audit-hardening/audit/critical_remediation_proof.md`
- `specs/036-owasp-audit-hardening/audit/backend_audit.md`
- `services/api/tests/unit/test_agent_guardrail_hitl_contract.py`
- `uis/backoffice/tsconfig.tsbuildinfo` (reversión)

**Tests to add or update**:
- Test en `test_agent_guardrail_hitl_contract.py` o `test_agent_guardrails_authorization.py` que compruebe que llamadas no autenticadas a `/actions/review` retornan `HTTP 401 Unauthorized` o `HTTP 403 Forbidden`.
- Test de integración verificando que una tool ejecutada por el agente con un `order_id` ajeno a la sesión es bloqueada por `validate_tool_call_authorization`.
- Test de script `test_verify_hardening_strictly_checks_system` asegurando que no valida positivamente si `/etc/ssh/sshd_config` no cumple.

## Risks & Considerations

- **Retrocompatibilidad en frontend/backoffice**: Si algún componente del Backoffice o test existente llamaba a `/actions/review` sin token JWT, fallará con 401; se debe asegurar el paso de credenciales o cabeceras Bearer en las pruebas.
- **Entorno CI para `verify_hardening.sh`**: Si los runners de CI ejecutan `verify_hardening.sh` sin privilegios de root ni servicio SSH activo, el script fallará. Se debe contemplar un parámetro explícito para validación estricta de host vs validación de plantillas en CI.

## Open Questions

- Ninguna pregunta abierta identificada. La especificación y los esquemas requeridos ya están definidos en el monorepo.
