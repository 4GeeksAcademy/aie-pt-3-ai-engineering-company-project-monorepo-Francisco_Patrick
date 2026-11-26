# Bug Assessment: Incomplete AI Systems Inventory and Unwired High-Value Dispatch HITL Gate

- **Slug**: ai-inventory-and-dispatch-gate
- **Created**: 2026-11-25
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> el inventario solo cataloga 5 sistemas y omite componentes ya construidos: el flujo RFP (intake, generación y aprobación), el chat WebSocket, la memoria del agente y la predicción de ventas. El criterio pide cada componente. Además, el despacho de alto valor solo existe como método en AgentActionPoliciesService; no está cableado a ninguna ruta o tool real, así que no hay confirmación humana en la ejecución (return/carrier y cross-brand sí están cubiertos). Añade los sistemas al inventario y cablea el gate o retíralo de la lista.

## Symptom

1. **Incomplete AI Systems Inventory (`SC-001` / `FR-005`)**: The authoritative AI systems inventory (`specs/037-nist-security-practices/data/ai_systems_inventory.json`, exposed via `GET /api/v1/security-audit/ai-inventory`) only lists 5 components (`TF-AI-01-CX-AGENT`, `TF-AI-02-CARRIER-ENGINE`, `TF-AI-03-POLICIES-RAG`, `TF-AI-04-RETURN-ENGINE`, `TF-AI-05-MCP-SERVER`) and omits already-built AI/ML systems in the repository:
   - **RFP Workflow (Intake, Response Generation, and Approval Completion)**: `data/pipelines/rfp_intake/`, `data/pipelines/rfp_response_generation/`, `data/pipelines/rfp_approval_completion/`, and `services/api/presentation/api/v1/rfp.py`.
   - **WebSocket Streaming Chat**: `services/api/presentation/api/v1/agent.py` (`/chat/ws` & `/chat/ws-ticket`) and `services/api/infrastructure/messaging/agent_chat_event_broker.py`.
   - **Agent Memory & Self-Improvement**: `services/api/application/services/memory_service.py`, `services/api/application/services/memory_guardrails.py`, and `services/api/presentation/api/v1/memory.py`.
   - **Sales Forecasting / Prediction Pipeline**: `data/pipelines/sales_forecast/` (`model.py`, `evaluator.py`, `features.py`, `dataset.py`).
2. **Unwired High-Value Dispatch HITL Gate (`SC-004` / `FR-012`)**: While `AgentActionPoliciesService.evaluate_high_value_dispatch(...)` is defined in `services/api/application/services/agent_action_policies.py:194-271` and tested in unit tests (`services/api/tests/unit/test_agent_action_policies.py:112-145`), it is never invoked by `AuthorizationGuardrailValidator.validate_tool_call_authorization(...)` in `services/api/application/services/agent_guardrails.py:1424-1554`, nor by any runtime tool node (`agent_workflow.py`) or API endpoint. By contrast, `evaluate_return_approval`, `evaluate_carrier_reassignment`, and cross-brand metric isolation (`brand_id` check / `evaluate_cross_brand_metric_share`) are wired into `validate_tool_call_authorization`.

## Reproduction

1. Inspect `specs/037-nist-security-practices/data/ai_systems_inventory.json` or call `GET /api/v1/security-audit/ai-inventory` and observe that only 5 entries exist; RFP workflow (intake, generation, approval), WebSocket streaming chat, agent memory, and sales forecasting are missing, and `services/api/tests/unit/test_nist_ai_inventory.py:17` hardcodes `assert len(inventory) == 5`.
2. Search the repository for invocations of `evaluate_high_value_dispatch` (`git grep -n "evaluate_high_value_dispatch"`):
   - It only appears in `services/api/application/services/agent_action_policies.py:194` (definition) and `services/api/tests/unit/test_agent_action_policies.py` (direct unit test calls).
3. Inspect `AuthorizationGuardrailValidator.validate_tool_call_authorization` in `services/api/application/services/agent_guardrails.py:1485-1554`:
   - Lines `1487-1515` intercept `return_approval` / `return_tool` / `refund_amount_eur` via `policy_svc.evaluate_return_approval(...)`.
   - Lines `1517-1545` intercept `carrier_reassignment` / `carrier_tool` / `target_carrier` via `policy_svc.evaluate_carrier_reassignment(...)`.
   - Lines `1467-1483` enforce cross-brand metric isolation (`CROSS_BRAND_METRIC_ACCESS_DENIED`).
   - There is no branch for high-value dispatch (`high_value_dispatch`, `dispatch_tool`, `confirm_dispatch`, `declared_value_eur`, or `address_verified`), nor any route/service calling `evaluate_high_value_dispatch`.

## Suspected Code Paths

- `specs/037-nist-security-practices/data/ai_systems_inventory.json:1-92` — Only catalogs 5 AI systems (`TF-AI-01` through `TF-AI-05`), omitting the RFP workflow (intake, generation, approval), WebSocket streaming chat, agent memory system, and sales forecasting pipeline.
- `services/api/domain/agent/entities.py:1223-1228`, `services/api/presentation/schemas/security_audit.py:255-260`, and `specs/037-nist-security-practices/contracts/nist-security-schemas.json:38-43` — `AISystemArchitecture` enum allows `"AUTONOMOUS_AGENT"`, `"DECISION_ENGINE"`, `"RAG_PIPELINE"`, `"MCP_SERVER_TOOL"` (and can either classify the added systems under these existing categories or extend the enum if an `"ML_PIPELINE"` / `"STREAMING_INTERFACE"` / `"MEMORY_SUBSYSTEM"` literal is desired, though sticking to valid schema enums or updating the schema consistently across all three files is required).
- `services/api/tests/unit/test_nist_ai_inventory.py:14-75` — Hardcodes `assert len(inventory) == 5` and only checks `TF-AI-01` through `TF-AI-05`.
- `services/api/infrastructure/adapters/nist_governance_repository.py:45` and `services/api/presentation/api/v1/security_audit.py:160` — Docstrings reference "all 5 operational AI components".
- `specs/037-nist-security-practices/data/nist_csf_baseline.json:12` and `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md:52-62,327` — Governance baseline and security audit report reference 5 AI systems in the inventory.
- `services/api/application/services/agent_guardrails.py:1424-1554` — `AuthorizationGuardrailValidator.validate_tool_call_authorization` wires `evaluate_return_approval`, `evaluate_carrier_reassignment`, and cross-brand metric isolation (which can also delegate to `policy_svc.evaluate_cross_brand_metric_share` so audit logs are emitted consistently), but omits `evaluate_high_value_dispatch`.
- `services/api/presentation/schemas/security_audit.py:172-214` — `ActionParametersSchema` and `AgentGuardrailHITLPayload` include `"RETURN_APPROVAL"`, `"CARRIER_REASSIGNMENT"`, `"ORDER_LOOKUP"`, `"BRAND_METRIC_QUERY"`, but omit `"HIGH_VALUE_DISPATCH"` and dispatch parameters (`parcel_id`, `declared_value_eur`, `address_verified`).

## Root Cause Hypothesis

**Confidence: High.** During the implementation of `037-nist-security-practices`, the AI systems inventory was seeded strictly from the 4 "starting point" examples in Section 3 of `docs/cybersecurity-analysis/trackflow-BRIEFING.es.md` plus the MCP server (5 systems total), overlooking the requirement (`SC-001` / audit scope in Section 7: *"todo lo construido en tu fork"*) to catalog every AI/ML component built in the monorepo (RFP multi-agent workflow covering intake/generation/approval, WebSocket streaming chat, agent memory & self-improvement, and sales prediction). Similarly, `AgentActionPoliciesService.evaluate_high_value_dispatch` was implemented to satisfy `FR-012` (Section 5 of the briefing: *"Confirmar el despacho de un envío de alto valor sin validación adicional"*) and tested in isolation in `test_agent_action_policies.py`, but when runtime tool authorization was wired in `AuthorizationGuardrailValidator.validate_tool_call_authorization` (`agent_guardrails.py:1485-1546`), only return approval and carrier reassignment were hooked into `AgentActionPoliciesService`, leaving `evaluate_high_value_dispatch` unwired to any runtime tool execution path or API route.

## Proposed Remediation

**Preferred**:
1. **Expand the Authoritative AI Systems Inventory**:
   - Update `specs/037-nist-security-practices/data/ai_systems_inventory.json` to catalog all active AI/ML components built in the monorepo alongside the initial 5:
     - **RFP Multi-Agent Workflow (Intake, Generation & Approval)** (`TF-AI-06-RFP-WORKFLOW`, or split into intake/generation/approval if granular; covering `data/pipelines/rfp_intake`, `data/pipelines/rfp_response_generation`, `data/pipelines/rfp_approval_completion`, and `services/api/presentation/api/v1/rfp.py`, `architecture_type: "AUTONOMOUS_AGENT"`, `requires_hitl_gates: true`).
     - **WebSocket Streaming Chat & Event Broker** (`TF-AI-07-WEBSOCKET-CHAT`, `services/api/presentation/api/v1/agent.py` & `services/api/infrastructure/messaging/agent_chat_event_broker.py`, `architecture_type: "AUTONOMOUS_AGENT"`, `requires_hitl_gates: true`, `rate_limiting_enabled: true`).
     - **Agent Memory & Self-Improvement Subsystem** (`TF-AI-08-AGENT-MEMORY`, `services/api/application/services/memory_service.py` & `services/api/application/services/memory_guardrails.py`, `architecture_type: "AUTONOMOUS_AGENT"`, `requires_hitl_gates: true`, `rate_limiting_enabled: true`).
     - **Sales Forecasting & Regression Engine** (`TF-AI-09-SALES-FORECAST`, `data/pipelines/sales_forecast/model.py`, `architecture_type: "DECISION_ENGINE"`, `data_classification: "CONFIDENTIAL_B2B"`).
   - Update `specs/037-nist-security-practices/data/nist_csf_baseline.json`, `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md`, docstrings in `nist_governance_repository.py` and `security_audit.py`, and unit assertions in `services/api/tests/unit/test_nist_ai_inventory.py` to validate all 9 cataloged AI systems.
2. **Wire the High-Value Dispatch HITL Gate into Runtime Execution**:
   - In `AuthorizationGuardrailValidator.validate_tool_call_authorization` (`services/api/application/services/agent_guardrails.py`), wire `policy_svc.evaluate_high_value_dispatch(...)` when `normalized_tool in ("high_value_dispatch", "dispatch_tool", "confirm_dispatch", "parcel_dispatch")` or when `"declared_value_eur" in parameters` / `"address_verified" in parameters` (extracting `parcel_id = str(parameters.get("parcel_id") or order_id or "unknown")`, `declared_value_eur = float(parameters.get("declared_value_eur") or 0.0)`, and `address_verified = bool(parameters.get("address_verified", True))`). When `eval_res.decision == "PENDING_HUMAN_APPROVAL"`, return a `GuardrailEvaluationResult` with `action="block"`, `reason_code=eval_res.reason_code`, and `metadata={"human_review_queue_id": eval_res.human_review_queue_id}` (and also invoke `policy_svc.evaluate_cross_brand_metric_share` in the cross-brand check so all 4 gates in `AgentActionPoliciesService` are invoked at runtime).
   - Also expose or wire high-value dispatch evaluation in the operational tool/API layer (e.g., `ActionParametersSchema` / `AgentGuardrailHITLPayload` in `services/api/presentation/schemas/security_audit.py` and an operational dispatch evaluation/confirmation endpoint or tool dispatch handler in `services/api/presentation/api/v1/agent.py` / `agent_workflow.py`) so that both agent tool calls and direct API dispatch actions enforce the HITL gate in runtime execution.

**Alternatives** (optional):
- **Remove High-Value Dispatch from the HITL Gate List**: As noted in the prompt (*"cablea el gate o retíralo de la lista"*), instead of wiring `evaluate_high_value_dispatch` to a tool/route, remove `HIGH_VALUE_DISPATCH` from `AgentActionPoliciesService`, `nist_csf_baseline.json`, `spec.md`, `nist-security-schemas.json`, and `owasp-top10-security-audit-report.md`. However, because Section 5 of `docs/cybersecurity-analysis/trackflow-BRIEFING.es.md` explicitly lists *"Confirmar el despacho de un envío de alto valor sin validación adicional"* as one of the 4 irreversible actions requiring human confirmation, **wiring the gate into runtime execution is strongly preferred** over removing it.

**Files likely to change**:
- `specs/037-nist-security-practices/data/ai_systems_inventory.json`
- `specs/037-nist-security-practices/data/nist_csf_baseline.json`
- `services/api/infrastructure/adapters/nist_governance_repository.py`
- `services/api/presentation/api/v1/security_audit.py`
- `services/api/application/services/agent_guardrails.py`
- `services/api/presentation/schemas/security_audit.py`
- `services/api/tests/unit/test_nist_ai_inventory.py`
- `services/api/tests/unit/test_agent_guardrails_authorization.py`
- `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md`

**Tests to add or update**:
- Update `services/api/tests/unit/test_nist_ai_inventory.py` to assert all 9 operational AI systems (including RFP workflow, WebSocket chat, Agent Memory, and Sales Forecast) are present, schema-valid, and mapped to internal custodians and attack surfaces.
- Add `test_tool_call_authorization_high_value_dispatch_hitl` and `test_tool_call_authorization_unverified_address_dispatch_hitl` in `services/api/tests/unit/test_agent_guardrails_authorization.py` verifying that `validate_tool_call_authorization` intercepts high-value (> 500 EUR) or unverified-address dispatches in runtime, transitions them to `PENDING_HUMAN_APPROVAL` in `AgentActionPoliciesService`, and blocks autonomous tool execution with `human_review_queue_id`.
- Add a runtime workflow/node test verifying that a dispatch tool call through the agent workflow / guardrail layer is intercepted and queued for human review.

## Risks & Considerations

- **Schema & Enum Alignment**: Every new record in `ai_systems_inventory.json` must strictly match `AISystemRecordSchema` (`system_id` regex `^TF-AI-[0-9]{2}-[A-Z0-9-]+$`, `architecture_type`, `data_classification`) so contract validation in `GET /api/v1/security-audit/ai-inventory` passes without error.
- **Order Authorization vs. Parcel ID in `validate_tool_call_authorization`**: When `validate_tool_call_authorization` checks `high_value_dispatch`, a call may pass `parcel_id` and/or `order_id`. If `order_id` is passed, session ownership is verified first; if only `parcel_id` is passed without `order_id`, the high-value dispatch HITL gate still evaluates `parcel_id`, `declared_value_eur`, and `address_verified` without false-negative bypass.

## Open Questions

- None — the codebase evidence and briefing requirements clearly specify both the 4 missing AI system families to add to the inventory and how `evaluate_high_value_dispatch` should be wired into runtime execution.
