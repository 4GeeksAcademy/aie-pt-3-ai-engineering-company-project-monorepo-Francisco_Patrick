# Bug Fix: Incomplete AI Systems Inventory and Unwired High-Value Dispatch HITL Gate

- **Slug**: ai-inventory-and-dispatch-gate
- **Fixed**: 2026-11-25
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Expanded the authoritative AI systems inventory (`specs/037-nist-security-practices/data/ai_systems_inventory.json`) from 5 to 9 cataloged AI/ML components to cover all systems built in the monorepo (RFP multi-agent workflow, WebSocket streaming chat, agent memory subsystem, and sales forecasting pipeline), and wired `AgentActionPoliciesService.evaluate_high_value_dispatch` into runtime tool execution (`AuthorizationGuardrailValidator.validate_tool_call_authorization` and LangGraph workflow tool nodes) as well as the operational HITL endpoint (`POST /api/v1/agent/actions/dispatch`).

## Changes

| File | Change | Notes |
|------|--------|-------|
| `specs/037-nist-security-practices/data/ai_systems_inventory.json` | modified | Added `TF-AI-06-RFP-WORKFLOW`, `TF-AI-07-WEBSOCKET-CHAT`, `TF-AI-08-AGENT-MEMORY`, and `TF-AI-09-SALES-FORECAST` (9 systems total). |
| `specs/037-nist-security-practices/data/nist_csf_baseline.json` | modified | Updated `GV.OC-01` operational action description to reflect all 9 cataloged production AI subsystems. |
| `services/api/infrastructure/adapters/nist_governance_repository.py` | modified | Updated `list_ai_inventory` docstring to reference all 9 operational AI components. |
| `services/api/presentation/api/v1/security_audit.py` | modified | Updated `list_ai_systems_inventory` docstring to reference all 9 operational AI components. |
| `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md` | modified | Added MCP Server, RFP Multi-Agent Workflow, WebSocket Chat, Agent Memory, and Sales Forecast to the Section 2 inventory table and updated Section 11.1 NIST CSF `Govern (GV)` summary to 9 AI systems. |
| `services/api/application/services/agent_guardrails.py` | modified | Wired `policy_svc.evaluate_high_value_dispatch(...)` and `policy_svc.evaluate_cross_brand_metric_share(...)` inside `AuthorizationGuardrailValidator.validate_tool_call_authorization`. |
| `services/api/application/services/agent_workflow.py` | modified | Forwarded runtime action parameters (`parcel_id`, `declared_value_eur`, `address_verified`, `refund_amount_eur`, `target_carrier`, `shipment_status`, `brand_id`) from `AgentState` into `validate_tool_call_authorization` in `ticket_tool_node` and `inventory_tool_node`. |
| `services/api/presentation/schemas/security_audit.py` | modified | Added `"HIGH_VALUE_DISPATCH"` to `AgentGuardrailHITLPayload.action_type`, added `parcel_id`, `declared_value_eur`, and `address_verified` to `ActionParametersSchema`, and added `HighValueDispatchEvaluationRequest`. |
| `specs/036-owasp-audit-hardening/contracts/agent-guardrail-hitl.schema.json` | modified | Added `"HIGH_VALUE_DISPATCH"` and dispatch fields (`parcel_id`, `declared_value_eur`, `address_verified`) to the HITL contract JSON Schema. |
| `services/api/presentation/api/v1/agent.py` | modified | Added `POST /api/v1/agent/actions/dispatch` endpoint to evaluate and gate high-value (> 500 EUR) or unverified-address parcel dispatches at runtime. |
| `services/api/tests/unit/test_nist_ai_inventory.py` | modified | Updated inventory completeness and custodian/attack-surface assertions to validate all 9 AI systems (`TF-AI-01` through `TF-AI-09`). |
| `services/api/tests/unit/test_agent_guardrails_authorization.py` | modified | Added `test_tool_call_authorization_high_value_dispatch_hitl`, `test_tool_call_authorization_unverified_address_dispatch_hitl`, and `test_runtime_inventory_tool_node_blocks_high_value_dispatch_for_hitl`. |
| `services/api/tests/unit/test_agent_guardrail_hitl_contract.py` | modified | Added `test_high_value_dispatch_contract_and_endpoint_hitl_gate` testing contract validation and `POST /api/v1/agent/actions/dispatch` queue integration. |

## Diff Highlights (optional)

```python
# services/api/application/services/agent_guardrails.py
if (
    normalized_tool in ("high_value_dispatch", "dispatch_tool", "confirm_dispatch", "parcel_dispatch")
    or "declared_value_eur" in parameters
    or "address_verified" in parameters
):
    from application.services.agent_action_policies import (
        get_agent_action_policies_service,
    )

    policy_svc = get_agent_action_policies_service()
    parcel_id = str(parameters.get("parcel_id") or order_id or "unknown")
    declared_value_eur = float(parameters.get("declared_value_eur") or 0.0)
    address_verified = (
        bool(parameters["address_verified"])
        if "address_verified" in parameters and parameters["address_verified"] is not None
        else True
    )
    eval_res = policy_svc.evaluate_high_value_dispatch(
        session_context=session_context,
        parcel_id=parcel_id,
        declared_value_eur=declared_value_eur,
        address_verified=address_verified,
    )
    if eval_res.decision == "PENDING_HUMAN_APPROVAL":
        ...
        return GuardrailEvaluationResult(
            layer="authorization_guard",
            action="block",
            failure_category="security",
            input_category="policy_mismatch",
            reason_code=eval_res.reason_code or "HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL",
            message=msg,
            metadata={"human_review_queue_id": eval_res.human_review_queue_id},
        )
```

## Tests Added or Updated

- `services/api/tests/unit/test_nist_ai_inventory.py::test_ai_systems_inventory_catalog_completeness` — Asserts all 9 operational AI components (`TF-AI-01` through `TF-AI-09`) are cataloged and validate against `AISystemRecordSchema`.
- `services/api/tests/unit/test_nist_ai_inventory.py::test_ai_systems_custodian_teams_and_technical_leads` — Verifies custodian teams, technical leads, data classifications, architecture types, HITL flags, and attack surfaces for all 9 systems including RFP workflow, WebSocket chat, Agent Memory, and Sales Forecast.
- `services/api/tests/unit/test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_tool_call_authorization_high_value_dispatch_hitl` — Verifies `validate_tool_call_authorization` blocks dispatches > 500 EUR with `HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL` and `human_review_queue_id`, while allowing verified dispatches <= 500 EUR.
- `services/api/tests/unit/test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_tool_call_authorization_unverified_address_dispatch_hitl` — Verifies unverified-address dispatches are intercepted and queued for human review even when declared value is <= 500 EUR.
- `services/api/tests/unit/test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_runtime_inventory_tool_node_blocks_high_value_dispatch_for_hitl` — Verifies `inventory_tool_node` intercepts high-value dispatch tool execution in runtime and transitions to refusal with `HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL`.
- `services/api/tests/unit/test_agent_guardrail_hitl_contract.py::test_high_value_dispatch_contract_and_endpoint_hitl_gate` — Verifies `HIGH_VALUE_DISPATCH` contract validation and `POST /api/v1/agent/actions/dispatch` integration with the supervisor review queue (`GET /api/v1/agent/actions/review`).

## Local Verification

- Commands run: `uv run --project services/api pytest services/api/tests/unit/test_nist_ai_inventory.py services/api/tests/unit/test_agent_guardrails_authorization.py services/api/tests/unit/test_agent_guardrail_hitl_contract.py services/api/tests/unit/test_agent_action_policies.py services/api/tests/unit/test_agent_workflow.py services/api/tests/integration/test_nist_csf_report_api.py -v` → `50 passed in 1.71s`
- Manual checks: Verified `specs/037-nist-security-practices/data/ai_systems_inventory.json` and `specs/037-nist-security-practices/data/nist_csf_baseline.json` parse cleanly and validate against `AISystemRecordSchema` and `NISTAssessmentReportResponse`.

## Deviations from Assessment

None.

## Follow-ups

- Run `/speckit-bug-test slug=ai-inventory-and-dispatch-gate` to record the formal verification report in `.specify/bugs/ai-inventory-and-dispatch-gate/verification.md`.
