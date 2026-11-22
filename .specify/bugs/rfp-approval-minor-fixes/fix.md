# Bug Fix: RFP Approval Initial Arbitration Default & Reject Feedback Validation

- **Slug**: rfp-approval-minor-fixes
- **Fixed**: 2026-11-22
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Configured `RFPApprovalService.enter_approval_milestone` and checkpoint initialization to enable `run_initial_arbitration=True` by default, ensuring cross-department conflicts are resolved before department heads review proposals. Aligned resume decision validation across pipeline validators, Pydantic schemas, JSON Schema contracts, and backoffice UI components to enforce non-empty feedback when `decision` is `reject` or `request_changes`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/agent/rfp_approval_service.py` | modified | Defaulted `run_initial_arbitration` to `True` in `enter_approval_milestone` and passed `run_initial_arbitration=True` in `_initialize_pending_branch_checkpoints`. |
| `data/pipelines/rfp_approval_completion/pipeline.py` | modified | Updated `validate_resume_decision()` to enforce non-empty feedback (min 5 chars) when `decision in ("request_changes", "reject")`. |
| `services/api/presentation/schemas/rfp.py` | modified | Updated `ResumeDecisionRequest` field description and model validator to require feedback for both `request_changes` and `reject`. |
| `specs/033-rfp-approval-completion/contracts/resume-decision.schema.json` | modified | Updated `allOf` conditional validation to require `feedback` (min 5 chars) when `decision` is `request_changes` or `reject`. |
| `uis/backoffice/components/rfp/DepartmentApprovalPanel.tsx` | modified | Enforced mandatory rejection reason in UI before submission and updated placeholder text. |
| `uis/backoffice/__tests__/DepartmentApprovalPanel.test.tsx` | modified | Added test `T030` asserting feedback requirement when `reject` is clicked. |
| `tests/pipelines/test_rfp_approval_interrupts.py` | modified | Added assertions for `reject` validation in `validate_resume_decision` and `ResumeDecisionRequest`, plus added `test_enter_approval_milestone_defaults_to_initial_arbitration`. |

## Diff Highlights

```python
# services/api/application/agent/rfp_approval_service.py
    def enter_approval_milestone(
        self,
        ticket_id: UUID,
-       run_initial_arbitration: bool = False,
+       run_initial_arbitration: bool = True,
    ) -> Dict[str, Any]:
```

```python
# data/pipelines/rfp_approval_completion/pipeline.py
    feedback = payload.get("feedback")
-   if decision == "request_changes":
+   if decision in ("request_changes", "reject"):
        if not isinstance(feedback, str) or len(feedback.strip()) < 5:
            raise ResumeValidationError(
-               "Non-empty revision 'feedback' (minimum 5 characters) is mandatory when decision is 'request_changes'."
+               f"Non-empty revision 'feedback' (minimum 5 characters) is mandatory when decision is '{decision}'."
            )
```

```json
// specs/033-rfp-approval-completion/contracts/resume-decision.schema.json
  "allOf": [
    {
      "if": {
        "properties": {
-         "decision": { "const": "request_changes" }
+         "decision": { "enum": ["request_changes", "reject"] }
        }
      },
```

## Tests Added or Updated

- `tests/pipelines/test_rfp_approval_interrupts.py::test_resume_input_validation_and_decision_routing` — asserts `ResumeValidationError` is raised when `decision == "reject"` lacks feedback, valid reject feedback succeeds, and `ResumeDecisionRequest` validates feedback for reject.
- `tests/pipelines/test_rfp_approval_interrupts.py::test_enter_approval_milestone_defaults_to_initial_arbitration` — verifies `enter_approval_milestone()` without explicit arguments executes initial arbitration by default, recording the `volume-vs-capacity` conflict log and adjusting the draft content.
- `uis/backoffice/__tests__/DepartmentApprovalPanel.test.tsx::T030` — verifies the backoffice UI prevents submitting a rejection without explaining the reason (minimum 5 characters).

## Local Verification

- Commands run:
  - `python -m pytest -k "rfp" tests/pipelines/` → 47 passed, 45 deselected (0 failures).
  - `npm.cmd --prefix uis/backoffice test -- --watchAll=false` → 12 test suites passed, 62 tests passed.
  - `npm.cmd --prefix uis/backoffice run typecheck` → TypeScript compiler clean with 0 errors.

## Deviations from Assessment

None. All changes adhere strictly to the preferred remediation in `assessment.md`.

## Follow-ups

- None required. All tests pass and contracts are fully synchronized across Python, TypeScript, JSON Schema, and React frontend components.
