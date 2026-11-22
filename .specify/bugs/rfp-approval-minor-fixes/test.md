# Bug Verification: RFP Approval Initial Arbitration Default & Reject Feedback Validation

- **Slug**: rfp-approval-minor-fixes
- **Tested**: 2026-11-22T13:04:00+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The fixes applied for both issues were verified end-to-end. Calling `RFPApprovalService.enter_approval_milestone` defaults to initial arbitration, resolving cross-department draft conflicts before human review; rejection submissions without feedback are strictly blocked across the pipeline, Pydantic schemas, and backoffice UI with no regressions detected.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix): Issue 1 | Inspect `enter_approval_milestone` signature and verify default arbitration run on ticket entry | pass | Default parameter is `run_initial_arbitration=True`; initial cross-department conflicts are arbitrated upfront. |
| Reproduction (post-fix): Issue 2 | Attempt `decision: "reject"` without feedback payload in pipeline and Pydantic validators | pass | `validate_resume_decision` raises `ResumeValidationError` and `ResumeDecisionRequest` raises Pydantic `ValidationError`. |
| New / updated tests | `services/api/.venv/Scripts/python.exe -m pytest tests/pipelines/test_rfp_approval_interrupts.py -v` | pass | 5/5 tests passed (including `test_enter_approval_milestone_defaults_to_initial_arbitration` and reject validation assertions). |
| Regression suite (Pipelines) | `services/api/.venv/Scripts/python.exe -m pytest tests/pipelines/ -k "rfp" -v` | pass | 47 passed, 45 deselected in 16.87s. |
| Regression suite (UI) | `npm.cmd --prefix uis/backoffice test -- --watchAll=false` | pass | 12 test suites passed, 62 tests passed (including `DepartmentApprovalPanel.test.tsx::T030`). |
| Lint / type-check | `npm.cmd --prefix uis/backoffice run typecheck` | pass | Clean TypeScript compilation with 0 errors. |

## Output Excerpts

### Reproduction Check
```text
Check 1: enter_approval_milestone default is True
Check 2a: validate_resume_decision reject without feedback raised: Non-empty revision 'feedback' (minimum 5 characters) is mandatory when decision is 'reject'.
Check 2b: ResumeDecisionRequest reject without feedback raised ValidationError
Check 2c: reject with feedback >= 5 chars passes both validations
ALL DIRECT CHECKS PASSED
```

### Python Test Suite
```text
tests/pipelines/test_rfp_approval_interrupts.py::test_scoped_interrupts_and_parallel_branch_independence PASSED [ 20%]
tests/pipelines/test_rfp_approval_interrupts.py::test_checkpointer_thread_namespacing_and_persistence PASSED [ 40%]
tests/pipelines/test_rfp_approval_interrupts.py::test_resume_input_validation_and_decision_routing PASSED [ 60%]
tests/pipelines/test_rfp_approval_interrupts.py::test_resume_request_changes_revises_branch_without_rerunning_upstream PASSED [ 80%]
tests/pipelines/test_rfp_approval_interrupts.py::test_enter_approval_milestone_defaults_to_initial_arbitration PASSED [100%]
============================== 5 passed in 2.96s ==============================
```

### Monorepo Backoffice Tests and Type Check
```text
Test Suites: 12 passed, 12 total
Tests:       62 passed, 62 total
Snapshots:   0 total
Time:        3.166 s
Ran all test suites.

> @trackflow/backoffice@1.0.0 typecheck
> tsc --noEmit
```

## Residual Risks

- None. The lower-level `data/pipelines/rfp_approval_completion/pipeline.py:start_approval_phase` preserves `run_initial_arbitration=False` as default to protect isolated unit test harnesses, while all operational entrypoints in `RFPApprovalService` explicitly enable it by default.

## Recommendation

Close the bug — verified end-to-end. Both initial arbitration gating and mandatory feedback validation for rejection are active, strictly validated, and verified across all tests.
