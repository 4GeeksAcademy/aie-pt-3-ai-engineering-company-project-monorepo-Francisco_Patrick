# Bug Verification: Incomplete AI Systems Inventory and Unwired High-Value Dispatch HITL Gate

- **Slug**: ai-inventory-and-dispatch-gate
- **Tested**: 2026-11-25
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

Both symptoms from the assessment are resolved and no longer reproduce: the authoritative AI systems inventory (`specs/037-nist-security-practices/data/ai_systems_inventory.json` and `GET /api/v1/security-audit/ai-inventory`) now catalogs all 9 operational AI/ML subsystems built in the monorepo (adding RFP Multi-Agent Workflow, WebSocket Streaming Chat, Agent Memory Subsystem, and Sales Forecasting Pipeline), and `AgentActionPoliciesService.evaluate_high_value_dispatch` is wired into runtime tool execution (`AuthorizationGuardrailValidator.validate_tool_call_authorization` and `inventory_tool_node` / `ticket_tool_node`) as well as the operational HITL endpoint (`POST /api/v1/agent/actions/dispatch`). All 50 unit, contract, and integration tests across the modified modules pass with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `git grep -n "evaluate_high_value_dispatch"` & `test_nist_ai_inventory.py` | pass | Confirmed all 9 AI systems (`TF-AI-01` through `TF-AI-09`) are present and schema-valid in `ai_systems_inventory.json`, and `evaluate_high_value_dispatch` is wired in `agent_guardrails.py:1544` and `agent.py:1364,1380`. |
| New / updated tests | `uv run --project services/api pytest services/api/tests/unit/test_nist_ai_inventory.py services/api/tests/unit/test_agent_guardrails_authorization.py services/api/tests/unit/test_agent_guardrail_hitl_contract.py -v` | pass | 26 passed — verified all 9 AI inventory records, runtime `validate_tool_call_authorization` & `inventory_tool_node` HITL interception for high-value (> 500 EUR) and unverified-address dispatches, and `POST /api/v1/agent/actions/dispatch`. |
| Regression suite | `uv run --project services/api pytest services/api/tests/unit/test_agent_action_policies.py services/api/tests/unit/test_agent_workflow.py services/api/tests/integration/test_nist_csf_report_api.py -v` | pass | 24 passed (50 total across combined suite in 1.43s) — zero regressions in agent action policies, LangGraph workflow nodes, or NIST CSF 2.0 reporting endpoints. |
| Lint / type-check | `uv run --project services/api python -m py_compile services/api/application/services/agent_guardrails.py services/api/application/services/agent_workflow.py services/api/presentation/api/v1/agent.py services/api/presentation/api/v1/security_audit.py services/api/presentation/schemas/security_audit.py services/api/infrastructure/adapters/nist_governance_repository.py services/api/tests/unit/test_nist_ai_inventory.py services/api/tests/unit/test_agent_guardrails_authorization.py services/api/tests/unit/test_agent_guardrail_hitl_contract.py` | pass | All modified source and test files compile cleanly with zero syntax or import errors. |

## Output Excerpts

```text
$ git grep -n "evaluate_high_value_dispatch" services/api/
services/api/application/services/agent_action_policies.py:194:    def evaluate_high_value_dispatch(
services/api/application/services/agent_guardrails.py:1544:            eval_res = policy_svc.evaluate_high_value_dispatch(
services/api/presentation/api/v1/agent.py:1364:async def evaluate_high_value_dispatch_action(
services/api/presentation/api/v1/agent.py:1380:        policy_service.evaluate_high_value_dispatch,
```

```text
services\api\tests\unit\test_nist_ai_inventory.py::test_ai_systems_inventory_catalog_completeness PASSED [  2%]
services\api\tests\unit\test_nist_ai_inventory.py::test_ai_systems_custodian_teams_and_technical_leads PASSED [  4%]
...
services\api\tests\unit\test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_tool_call_authorization_high_value_dispatch_hitl PASSED [ 34%]
services\api\tests\unit\test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_tool_call_authorization_unverified_address_dispatch_hitl PASSED [ 36%]
services\api\tests\unit\test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_runtime_inventory_tool_node_blocks_high_value_dispatch_for_hitl PASSED [ 38%]
...
services\api\tests\unit\test_agent_guardrail_hitl_contract.py::test_high_value_dispatch_contract_and_endpoint_hitl_gate PASSED [ 52%]
...
======================= 50 passed, 2 warnings in 1.43s ========================
```

## Residual Risks

- New AI/ML subsystems added to the monorepo in future features must be registered in `specs/037-nist-security-practices/data/ai_systems_inventory.json` and covered in `services/api/tests/unit/test_nist_ai_inventory.py` to maintain 100% inventory completeness (`SC-001`).

## Recommendation

Close the bug — verified end-to-end. Both the 9-system AI inventory (`TF-AI-01` through `TF-AI-09`) and the runtime high-value/unverified-address dispatch HITL gate (`validate_tool_call_authorization`, `inventory_tool_node`, and `POST /api/v1/agent/actions/dispatch`) are verified by automated unit, contract, and integration checks.
