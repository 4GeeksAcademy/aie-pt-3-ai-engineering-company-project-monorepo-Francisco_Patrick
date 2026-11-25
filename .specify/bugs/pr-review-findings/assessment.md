# Bug Assessment: Technical Review Findings for NIST Security Practices & AI Governance PR

- **Slug**: pr-review-findings
- **Created**: 2026-11-25
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: medium

## Report (verbatim or summarized)

```markdown
# Hallazgos técnicos y observaciones a revisar

1. **Trazabilidad en runtime (`AC-8`):** Aunque `GuardrailObservabilityService` ya almacena `SecurityAuditLogEntry`, en el diff no se muestra que el orquestador del agente o las políticas emitan `record_security_audit_log(...)` durante el flujo real ni hay un test que lo aserte.
2. **Inconsistencia menor en `HITLReviewDecisionRequestSchema` (`services/api/presentation/schemas/agent.py`):** El schema acepta `reviewer_id` en el cuerpo de la petición, pero en `submit_supervisor_action_review` (`agent.py`) se sobrescribe `reviewer` con `current_user.email or current_user.id` (bueno para anti-spoofing, pero conviene alinearlo o documentarlo para no generar confusión en el contrato).
3. **Encoding / caracteres corruptos en el diff:** En varios archivos (`c2995e90-...pdf`, `incident-response-gdpr-72h.md`, `owasp-top10-security-audit-report.md`, `carrier_service.py`, `test_nist_gdpr_incident_sla.py`, `research.md`) aparecen caracteres `ÔÇö`, `├│`, `├í`, etc., probablemente por codificación al generar/pegar el diff o leer UTF-8 como CP1252/Latin-1. Revisar que los archivos en disco estén guardados en **UTF-8** limpio.
4. **Archivo PDF en `data/raw/`:** Se añade `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf` como texto plano en el diff; verificar si es un fixture de prueba intencional para esta PR.
```

## Symptom

1. **Runtime Security Audit Traceability (`AC-8` / `FR-011`)**: `GuardrailObservabilityService` implements `record_security_audit_log(entry: SecurityAuditLogEntry)` and `list_security_audit_logs(...)`, and `GuardrailObservabilityService.clear()` fails to clear `self._audit_logs`, yet neither `AgentActionPoliciesService`, `SupportAgentService`, nor `agent_workflow.py` invokes `record_security_audit_log(...)` during actual execution, and no unit/integration test asserts runtime emission of `SecurityAuditLogEntry`.
2. **HITL Review Contract Anti-Spoofing Alignment**: `HITLReviewDecisionRequestSchema` (`services/api/presentation/schemas/agent.py`) and `HITLReviewDecisionRequest` (`services/api/presentation/schemas/security_audit.py`), as well as `specs/037-nist-security-practices/contracts/nist-governance-api.openapi.json`, require `reviewer_id: str` in the request payload even though `submit_supervisor_action_review` (`services/api/presentation/api/v1/agent.py:1193`) overwrites it with `current_user.email or current_user.id` for anti-spoofing (whereas `HumanApprovalDecisionRequest` already makes `reviewer_id: Optional[str] = None`).
3. **UTF-8 Encoding Verification vs. Diff Mojibake**: The diff viewer rendered UTF-8 multibyte sequences (`—`, `ó`, `á`) as CP437/CP850/CP1252 mojibake (`ÔÇö`, `├│`, `├í`). Direct inspection of the files on disk confirms they are stored in clean UTF-8, though automated verification should ensure zero mojibake or BOM issues exist on disk.
4. **Stray Runtime PDF Upload in `data/raw/`**: `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf` is a binary RFP PDF upload generated with a random UUID prefix during an earlier RFP extraction run and is completely unrelated to `037-nist-security-practices`.

## Reproduction

1. **Finding 1 (`AC-8` Runtime Traceability)**:
   - Inspect `services/api/application/services/guardrail_observability.py:145-162`: `record_security_audit_log` and `list_security_audit_logs` are defined on `GuardrailObservabilityService` (and not declared on `GuardrailObservabilityPort` in `services/api/domain/agent/ports.py:388`).
   - Search across `services/api/` for any calls to `record_security_audit_log`: zero call sites exist in `agent_action_policies.py`, `agent_workflow.py`, `support_agent_service.py`, or `tests/`.
2. **Finding 2 (`HITLReviewDecisionRequestSchema` Contract Alignment)**:
   - Inspect `services/api/presentation/schemas/agent.py:615-621` (`HITLReviewDecisionRequestSchema`) and `services/api/presentation/api/v1/agent.py:1182-1201` (`submit_supervisor_action_review`).
   - Observe that `reviewer_id` is required (`str`) on `HITLReviewDecisionRequestSchema`, yet `submit_supervisor_action_review` ignores `review_req.reviewer_id` and assigns `reviewer = current_user.email or current_user.id`.
3. **Finding 3 (UTF-8 File Encoding on Disk)**:
   - Read `docs/cybersecurity-analysis/incident-response-gdpr-72h.md`, `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md`, `services/api/application/services/carrier_service.py`, `services/api/tests/unit/test_nist_gdpr_incident_sla.py`, and `specs/037-nist-security-practices/research.md` directly as UTF-8.
   - Observe that all files on disk contain valid UTF-8 characters (`—`, `ó`, `á`, `é`, `í`, `ú`, `ñ`); the mojibake `ÔÇö`, `├│`, `├í` occurred when the diff (`diff_branch.txt`) was generated or piped through a Windows console using CP850/CP437 encoding.
4. **Finding 4 (Unintended PDF in `data/raw/`)**:
   - Inspect `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf`.
   - Observe that it is a runtime-uploaded RFP PDF (`<uuid>_trackflow-request-1.pdf`) that is not referenced by any test or specification in `037-nist-security-practices`.

## Suspected Code Paths

- `services/api/application/services/guardrail_observability.py:145-162, 310-316` — `record_security_audit_log` and `list_security_audit_logs` are defined here, and `clear()` at line 310 does not clear `self._audit_logs`, nor is `record_security_audit_log` exposed on `GuardrailObservabilityPort`.
- `services/api/domain/agent/ports.py:388-421` — `GuardrailObservabilityPort` lacks abstract/default methods for `record_security_audit_log` and `list_security_audit_logs`.
- `services/api/application/services/agent_action_policies.py:30-294` — `AgentActionPoliciesService` evaluates all 4 irreversible action policies (`evaluate_return_approval`, `evaluate_high_value_dispatch`, `evaluate_carrier_reassignment`, `evaluate_cross_brand_metric_share`) and processes supervisor decisions (`review_pending_request`, `check_expirations`) without emitting `SecurityAuditLogEntry` records via `record_security_audit_log`.
- `services/api/application/services/agent_workflow.py:472-502, 747-798, 908-959, 1086-1101, 1621-1637` — Guardrail evaluations in `intake_node`, `ticket_tool_node`, `inventory_tool_node`, `retrieval_node`, and `generation_node` call `observability.record_evaluation(...)`, which records `GuardrailAuditEvent`, but neither `record_evaluation` nor the workflow/policy service emits `SecurityAuditLogEntry`.
- `services/api/presentation/schemas/agent.py:615-621` — `HITLReviewDecisionRequestSchema` defines `reviewer_id: str` as required without documenting or making it optional in light of JWT anti-spoofing override.
- `services/api/presentation/schemas/security_audit.py:320-329` — `HITLReviewDecisionRequest` also defines `reviewer_id: str` as required.
- `services/api/presentation/api/v1/agent.py:1182-1201` — `submit_supervisor_action_review` overrides `reviewer = current_user.email or current_user.id`.
- `specs/037-nist-security-practices/contracts/nist-governance-api.openapi.json:123-138` — OpenAPI spec lists `reviewer_id` under `required` without noting that the server resolves/overrides `reviewer_id` from the authenticated supervisor's Bearer JWT to prevent spoofing.
- `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf` — Unintended runtime PDF artifact tracked in `data/raw/`.

## Root Cause Hypothesis

**Confidence: High.**
1. For **Finding 1 (`AC-8`)**, `SecurityAuditLogEntry` and `GuardrailObservabilityService.record_security_audit_log()` were implemented during Phase 6 (`T030`), but the runtime wiring into `AgentActionPoliciesService` (when evaluating the 4 HITL action policies and supervisor review transitions) and/or `GuardrailObservabilityService.record_evaluation` / `SupportAgentService` was omitted, along with the corresponding unit/integration test assertions.
2. For **Finding 2**, `HITLReviewDecisionRequestSchema` was created from the initial OpenAPI schema where `reviewer_id` was a required string, while the endpoint implementation (`submit_supervisor_action_review`) rightly enforced anti-spoofing by deriving `reviewer` from `current_user.email or current_user.id` (matching `review_agent_action`).
3. For **Finding 3**, the files on disk are valid UTF-8, and the mojibake (`ÔÇö` = UTF-8 `E2 80 94` decoded as CP437/CP850; `├│` = UTF-8 `C3 B3` decoded as CP437/CP850; `├í` = UTF-8 `C3 A1` decoded as CP437/CP850) was an artifact of generating `diff_branch.txt` in a Windows shell without UTF-8 output encoding.
4. For **Finding 4**, `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf` was written to `data/raw/` during an RFP upload test/run and accidentally staged in git.

## Proposed Remediation

**Preferred**:
1. **Wire Runtime `SecurityAuditLogEntry` Emission & Tests (`AC-8` / `FR-011`)**:
   - Add `record_security_audit_log` and `list_security_audit_logs` to `GuardrailObservabilityPort` (`services/api/domain/agent/ports.py`) and ensure `GuardrailObservabilityService.clear()` also clears `self._audit_logs`.
   - Wire `AgentActionPoliciesService` (`services/api/application/services/agent_action_policies.py`) and `GuardrailObservabilityService.record_evaluation` (or `SupportAgentService` / `agent_workflow.py`) to emit structured, redacted `SecurityAuditLogEntry` records via `record_security_audit_log(...)` whenever an autonomous policy decision (`evaluate_return_approval`, `evaluate_high_value_dispatch`, `evaluate_carrier_reassignment`, `evaluate_cross_brand_metric_share`), supervisor review decision (`review_pending_request`), fail-secure timeout (`check_expirations`), or guardrail intervention occurs.
   - Add deterministic unit and integration assertions in `services/api/tests/unit/test_agent_action_policies.py`, `services/api/tests/unit/test_guardrail_observability_redaction.py`, and `services/api/tests/unit/test_agent_guardrail_hitl_contract.py` verifying that `record_security_audit_log` is called during real policy/agent execution flows and populates `list_security_audit_logs()`.
2. **Align `HITLReviewDecisionRequestSchema` & OpenAPI Contract with Anti-Spoofing Behavior**:
   - Make `reviewer_id: Optional[str] = Field(default=None, description="Optional supervisor ID; ignored/overridden in favor of authenticated JWT user identity (email/id) to prevent spoofing.")` in `HITLReviewDecisionRequestSchema` (`services/api/presentation/schemas/agent.py`) and `HITLReviewDecisionRequest` (`services/api/presentation/schemas/security_audit.py`).
   - Update `submit_supervisor_action_review` docstring in `services/api/presentation/api/v1/agent.py` and `specs/037-nist-security-practices/contracts/nist-governance-api.openapi.json` so `reviewer_id` is optional in the request body (backward-compatible if sent by existing clients, but documented as resolved from the authenticated Bearer JWT).
3. **Verify Clean UTF-8 Encoding Across All Modified Files**:
   - Ensure all modified files are saved in strict UTF-8 without BOM and add/run a check confirming zero mojibake sequences (`ÔÇö`, `├│`, `├í`, etc.) exist in any repository file on disk.
4. **Remove Unintended PDF Artifact from `data/raw/`**:
   - Remove `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf` (and ignore `data/raw/*.pdf` or runtime UUID uploads in `.gitignore` if appropriate) so the PR diff remains clean.

**Files likely to change**:
- `services/api/domain/agent/ports.py`
- `services/api/application/services/guardrail_observability.py`
- `services/api/application/services/agent_action_policies.py`
- `services/api/presentation/schemas/agent.py`
- `services/api/presentation/schemas/security_audit.py`
- `services/api/presentation/api/v1/agent.py`
- `specs/037-nist-security-practices/contracts/nist-governance-api.openapi.json`
- `services/api/tests/unit/test_agent_action_policies.py`
- `services/api/tests/unit/test_agent_guardrail_hitl_contract.py`
- `services/api/tests/unit/test_guardrail_observability_redaction.py`
- `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf` (delete)

**Tests to add or update**:
- Update `services/api/tests/unit/test_agent_action_policies.py` to assert that evaluating return approvals, high-value dispatches, in-transit carrier reassignments, cross-brand metric shares, and supervisor review decisions emits `SecurityAuditLogEntry` records via `record_security_audit_log(...)` with redacted input parameters, evaluated policy rules, decision outcomes, and rationale.
- Update `services/api/tests/unit/test_guardrail_observability_redaction.py` to test `record_security_audit_log` during guardrail evaluations and verify `clear()` resets `_audit_logs`.
- Update `services/api/tests/unit/test_agent_guardrail_hitl_contract.py` to verify that `POST /api/v1/agent/actions/review` works both with and without `reviewer_id` in the payload, always enforces anti-spoofing from the JWT user, and records a `SecurityAuditLogEntry`.

## Risks & Considerations

- **Backward Compatibility on `POST /api/v1/agent/actions/review`**: Making `reviewer_id` optional (`Optional[str] = None`) rather than removing or rejecting it preserves 100% backward compatibility with existing tests and clients that pass `reviewer_id`, while aligning the schema and OpenAPI documentation with the anti-spoofing JWT enforcement.
- **Singleton State Isolation in Tests**: Because `GuardrailObservabilityService` and `AgentActionPoliciesService` are used across tests, `GuardrailObservabilityService.clear()` must clear `_audit_logs` to prevent cross-test pollution.

## Open Questions

- None — all four findings are verified against the current codebase and have clear, deterministic remediations.
