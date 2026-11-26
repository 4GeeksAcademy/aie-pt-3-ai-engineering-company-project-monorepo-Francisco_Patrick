# Bug Fix: Technical Review Findings for NIST Security Practices & AI Governance PR

- **Slug**: pr-review-findings
- **Fixed**: 2026-11-25
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Wired runtime `SecurityAuditLogEntry` emission across `GuardrailObservabilityPort`, `GuardrailObservabilityService`, and `AgentActionPoliciesService` (including `clear()` isolation and PII/credential redaction), aligned `HITLReviewDecisionRequestSchema`, `HITLReviewDecisionRequest`, `submit_supervisor_action_review`, and `nist-governance-api.openapi.json` so `reviewer_id` is optional and documented as overridden by the authenticated supervisor's JWT identity, verified clean UTF-8 encoding without BOM or mojibake across all files on disk, and deleted the unintended `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf` artifact.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/domain/agent/ports.py` | modified | Added `record_security_audit_log` and `list_security_audit_logs` to `GuardrailObservabilityPort`. |
| `services/api/application/services/guardrail_observability.py` | modified | Wired `record_evaluation` to emit redacted `SecurityAuditLogEntry` records on guardrail interventions and updated `clear()` to clear `self._audit_logs`. |
| `services/api/application/services/agent_action_policies.py` | modified | Added `_emit_audit_log` and wired `evaluate_return_approval`, `evaluate_high_value_dispatch`, `evaluate_carrier_reassignment`, `evaluate_cross_brand_metric_share`, `check_expirations`, and `review_pending_request` to emit redacted `SecurityAuditLogEntry` records. |
| `services/api/presentation/schemas/agent.py` | modified | Made `reviewer_id` optional (`Optional[str] = None`) on `HITLReviewDecisionRequestSchema` and documented server-side JWT anti-spoofing override. |
| `services/api/presentation/schemas/security_audit.py` | modified | Made `reviewer_id` optional (`Optional[str] = None`) on `HITLReviewDecisionRequest` and documented server-side JWT anti-spoofing override. |
| `services/api/presentation/api/v1/agent.py` | modified | Documented anti-spoofing JWT derivation of `reviewer_id` in `submit_supervisor_action_review` docstring. |
| `specs/037-nist-security-practices/contracts/nist-governance-api.openapi.json` | modified | Removed `reviewer_id` from `required` in `/api/v1/agent/actions/review` requestBody and documented server-side Bearer JWT resolution. |
| `services/api/tests/unit/test_agent_action_policies.py` | added test | Added `test_runtime_security_audit_log_emission_across_policies_and_reviews` verifying runtime `SecurityAuditLogEntry` emission and PII/credential redaction across all 4 policies and supervisor reviews. |
| `services/api/tests/unit/test_guardrail_observability_redaction.py` | added test | Added `test_record_evaluation_emits_security_audit_log_and_clear_resets` verifying `record_evaluation` emits `SecurityAuditLogEntry` and `clear()` resets `_audit_logs`. |
| `services/api/tests/unit/test_agent_guardrail_hitl_contract.py` | modified | Extended `test_nist_governance_actions_review_post_endpoint` to verify `POST /api/v1/agent/actions/review` with spoofed `reviewer_id`, without `reviewer_id`, and assert `SecurityAuditLogEntry` records. |
| `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf` | removed | Deleted unintended runtime RFP PDF upload from `data/raw/`. |

## Diff Highlights (optional)

```python
# services/api/application/services/agent_action_policies.py
entry = SecurityAuditLogEntry(
    event_id=f"aud_{uuid.uuid4().hex[:12]}",
    timestamp=datetime.now(timezone.utc),
    agent_id="TF-AI-01-SUPPORT-AGENT",
    session_id=session_id,
    tenant_id=str(tenant_id),
    event_category=event_category,
    action_attempted=action_attempted,
    input_parameters_redacted=redacted_params,
    policy_rules_evaluated=list(policy_rules_evaluated),
    decision_outcome=decision_outcome,
    reasoning_rationale=sanitize_audit_preview(reasoning_rationale),
)
self.observability.record_security_audit_log(entry)
```

```python
# services/api/presentation/schemas/agent.py
class HITLReviewDecisionRequestSchema(BaseModel):
    """Supervisor review submission schema for HITL gates."""

    request_id: str = Field(description="UUID of pending review request")
    decision: Literal["APPROVE", "REJECT"] = Field(description="Supervisor decision")
    reviewer_id: Optional[str] = Field(
        default=None,
        description="Optional supervisor ID; ignored/overridden in favor of authenticated JWT user identity (email/id) to prevent spoofing.",
    )
    decision_notes: Optional[str] = Field(default=None, description="Operational justification notes")
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_action_policies.py::test_runtime_security_audit_log_emission_across_policies_and_reviews` — Pins down runtime `SecurityAuditLogEntry` emission and PII/carrier credential redaction across `evaluate_return_approval`, `evaluate_high_value_dispatch`, `evaluate_carrier_reassignment`, `evaluate_cross_brand_metric_share`, and `review_pending_request`.
- `services/api/tests/unit/test_guardrail_observability_redaction.py::test_record_evaluation_emits_security_audit_log_and_clear_resets` — Pins down `SecurityAuditLogEntry` creation during `GuardrailObservabilityService.record_evaluation` and verifies `clear()` resets `_audit_logs`.
- `services/api/tests/unit/test_agent_guardrail_hitl_contract.py::test_nist_governance_actions_review_post_endpoint` — Pins down `POST /api/v1/agent/actions/review` anti-spoofing when `reviewer_id` is provided, backward-compatible optionality when `reviewer_id` is omitted, and runtime `SecurityAuditLogEntry` recording.

## Local Verification

- Commands run:
  - `python -c "...UTF-8 and mojibake check..."` → `UTF-8 and mojibake check passed for all 12 files.`
  - `pytest services/api/tests/unit/test_agent_action_policies.py services/api/tests/unit/test_guardrail_observability_redaction.py services/api/tests/unit/test_agent_guardrail_hitl_contract.py services/api/tests/unit/test_nist_gdpr_incident_sla.py` → 18 passed in 0.44s
- Manual checks: Verified `data/raw/c2995e90-8a60-4761-b143-508cf4a801d4_trackflow-request-1.pdf` is removed from disk.

## Deviations from Assessment

None.

## Follow-ups

- Consider adding `data/raw/*.pdf` to `.gitignore` if runtime RFP PDF uploads are stored in `data/raw/` during local manual testing.
- Run `/speckit-bug-test slug=pr-review-findings` to record the verification report.
