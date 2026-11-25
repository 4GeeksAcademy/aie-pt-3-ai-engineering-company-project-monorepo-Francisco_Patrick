# Bug Fix: OWASP Hardening PR Findings & Pre-Merge Remediation

- **Slug**: owasp-hardening-pr-findings
- **Fixed**: 2026-11-25T01:00:00+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Applied comprehensive security remediations for the OWASP Top 10 hardening PR: secured human-in-the-loop (HITL) action review endpoints with supervisor role authorization and anti-spoofing reviewer extraction, wired runtime tool call authorization and action policy threshold gates into `agent_workflow.py` and `support_agent_service.py`, corrected host hardening script fallback to eliminate false positives on unconfigured servers, untracked binary build artifacts, and clarified pre-existing sanitized exception handling documentation.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/presentation/schemas/security_audit.py` | modified | Made `reviewer_id` optional in `HumanApprovalDecisionRequest` to enable strict server-side extraction from JWT. |
| `services/api/presentation/api/v1/agent.py` | modified | Added `Depends(get_current_user)` and `role in ("admin", "manager")` checks on `/actions/review` endpoints; typed payload with `HumanApprovalDecisionRequest`; enforced `reviewer_id = current_user.email`. |
| `services/api/application/services/agent_guardrails.py` | modified | Wired `validate_tool_call_authorization` to `AgentActionPoliciesService` for return approval threshold (>100 EUR) and in-transit carrier reassignment gates. |
| `services/api/application/services/agent_workflow.py` | modified | Injected `authorization_guard` into `ticket_tool_node` and `inventory_tool_node`; updated routing to direct blocked tool calls immediately to `refusal`. |
| `services/api/application/services/support_agent_service.py` | modified | Forwarded `_authorization_guard` to tool nodes during pre-generation streaming execution. |
| `infra/host/verify_hardening.sh` | modified | Eliminated false-positive repo template fallback in strict host mode; added explicit `--template-check` flag for CI/offline validation. |
| `.gitignore` | modified | Added `*.tsbuildinfo` to prevent committing TypeScript build caches. |
| `uis/backoffice/tsconfig.tsbuildinfo` | removed (untracked) | Removed compiled cache artifact from git index. |
| `specs/036-owasp-audit-hardening/audit/critical_remediation_proof.md` | modified | Clarified that sanitized 500 error handling in `core/exceptions.py` was pre-existing in `main` and verified via `test_error_handling_sanitization.py`. |
| `specs/036-owasp-audit-hardening/audit/backend_audit.md` | modified | Aligned SEC-BK-009 remediation notes with verification proof. |
| `services/api/tests/unit/test_agent_guardrail_hitl_contract.py` | modified | Added contract tests for 401 unauthenticated, 403 unauthorized role, and reviewer ID anti-spoofing on review endpoints. |
| `services/api/tests/unit/test_agent_guardrails_authorization.py` | modified | Added integration tests verifying runtime tool call authorization blocks unauthorized orders and triggers HITL review gates. |
| `services/api/tests/integration/test_host_hardening_verification.py` | modified | Added automated test ensuring `verify_hardening.sh` strictly inspects host configuration files without false-positive fallbacks. |

## Diff Highlights

### 1. Enforcing Authentication, Role Boundaries, and Anti-Spoofing on HITL Endpoints (`agent.py`)
```python
@router.post(
    "/actions/review/{request_id}",
    response_model=HumanApprovalGateResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or reject a queued agent action with reviewer notes",
)
async def review_agent_action(
    request_id: str,
    decision_req: HumanApprovalDecisionRequest = Body(...),
    current_user: User = Depends(get_current_user),
    policy_service: Any = Depends(get_agent_action_policies_service),
) -> HumanApprovalGateResponse:
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Supervisor or administrator role required.",
        )
    reviewer_id = current_user.email or current_user.id
    ...
```

### 2. Runtime Wiring of Tool Authorization & HITL Action Policies (`agent_workflow.py` & `agent_guardrails.py`)
```python
# In agent_workflow.py ticket_tool_node:
if authorization_guard is not None:
    auth_eval = authorization_guard.validate_tool_call_authorization(
        session_context=state.get("session_context"),
        tool_name="ticket_tool",
        parameters=tool_params,
        language=state.get("language") or "en",
    )
    if auth_eval.action == "block":
        return {
            "ticket_tool_output": TicketToolOutput(status="error", error_message=auth_eval.message, ...),
            "is_refusal": True,
            "guardrail_action": "block",
            "guardrail_reason_code": auth_eval.reason_code,
            "answer": auth_eval.message,
            ...
        }
```

### 3. Strict Host Hardening Verification Without False Positives (`verify_hardening.sh`)
```bash
# Explicit distinction between host validation and template validation
if [ "$TEMPLATE_CHECK" = true ]; then
    if grep -Eqi "^\s*PermitRootLogin\s+no" infra/host/sshd_config.hardened 2>/dev/null; then
        echo "PASS (template)"
...
else
    if [ -f "/etc/ssh/sshd_config" ] && grep -Eqi "^\s*PermitRootLogin\s+no" /etc/ssh/sshd_config 2>/dev/null; then
        echo "PASS"
...
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrail_hitl_contract.py::test_actions_review_endpoints_require_authentication` — Pins down HTTP 401 on unauthenticated calls to `/actions/review`.
- `services/api/tests/unit/test_agent_guardrail_hitl_contract.py::test_actions_review_endpoints_reject_non_supervisor_roles` — Pins down HTTP 403 on users with non-supervisor role (`user`).
- `services/api/tests/unit/test_agent_guardrail_hitl_contract.py::test_actions_review_endpoints_supervisor_decision_and_anti_spoofing` — Pins down supervisor review approval and prevents client tampering with `reviewer_id`.
- `services/api/tests/unit/test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_tool_call_authorization_high_value_return_hitl` — Pins down threshold gate (>100 EUR) for autonomous returns.
- `services/api/tests/unit/test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_tool_call_authorization_in_transit_carrier_reassignment_hitl` — Pins down in-transit carrier reassignment gate.
- `services/api/tests/unit/test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_runtime_ticket_tool_node_blocks_unauthorized_order` — Pins down runtime refusal when tool executes against an order outside session scope.
- `services/api/tests/integration/test_host_hardening_verification.py::test_verify_hardening_strictly_checks_system_without_false_positives` — Pins down strict `/etc/ssh/sshd_config` requirement and absence of template fallback without `--template-check`.

## Local Verification

- Commands run:
  - `uv run --project services/api pytest services/api/tests/unit/test_agent_guardrails_authorization.py services/api/tests/unit/test_agent_guardrail_hitl_contract.py services/api/tests/unit/test_agent_workflow.py services/api/tests/integration/test_host_hardening_verification.py services/api/tests/unit/test_error_handling_sanitization.py services/api/tests/unit/test_agent_action_policies.py -v` → 44 passed, 2 warnings in 1.24s
- Manual checks:
  - Validated git status: untracked `uis/backoffice/tsconfig.tsbuildinfo` cleanly and ignored in `.gitignore`.
  - Confirmed `verify_hardening.sh` runs cleanly in both strict mode and `--template-check` mode.

## Deviations from Assessment

None. All 5 findings identified in the assessment contract were directly resolved and validated.

## Follow-ups

- Ensure CI pipeline invokes `infra/host/verify_hardening.sh --template-check` during PR validation so template syntax is verified in unprivileged runner environments.
- Verify that deployment manifests pass supervisor JWT tokens when automated backoffice workers interact with `/api/v1/agent/actions/review`.
