# Bug Assessment: RFP Approval Initial Arbitration Default & Reject Feedback Validation

- **Slug**: rfp-approval-minor-fixes
- **Created**: 2026-11-22
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: low

## Report (verbatim or summarized)

The user reported two non-blocking minor bugs in the RFP approval completion workflow:

1. **Execution Order in `_evaluate_ticket_completion_gate()` (`pipeline.py`):**
   `evaluate_and_arbitrate_conflicts()` is executed both optionally in `start_approval_phase(..., run_initial_arbitration=True)` and at the end in `_evaluate_ticket_completion_gate()` once all departments have approved. If a cross-department conflict (e.g., `volume-vs-capacity` or `returns-sla-breach`) was not resolved upon entering Part 3, `_evaluate_ticket_completion_gate()` detects it prior to synthesis, forces `changes_requested`, and reverts the ticket to `esperando_aprobación`. Ensuring that `enter_approval_milestone()` invokes `run_initial_arbitration=True` by default in the service/endpoint prevents a department head from approving a draft that is subsequently invalidated by arbitration.

2. **Validation of `feedback` in `reject` vs `request_changes`:**
   In `validate_resume_decision()` (`pipeline.py`), `feedback` is mandatory for `request_changes` and optional for `reject`. However, the docstring of `ResumeDecisionRequestDTO` in `packages/shared/types/rfp.ts` and the description in `specs/033-rfp-approval-completion/contracts/resume-decision.schema.json` mention *"Mandatory feedback if decision is 'request_changes' or 'reject'"*. There is a slight divergence between the DTO comment and the backend/Pydantic validators.

## Symptom

- **Issue 1**: When tickets enter Part 3 without initial arbitration enabled by default, initial department drafts can contain cross-department conflicts. If approvers submit approvals on those conflicting drafts, the completion gate `_evaluate_ticket_completion_gate()` runs arbitration, discovers the discrepancy post-approval, sets the status back to `changes_requested`, and invalidates their prior approval after the fact.
- **Issue 2**: Approvers or API consumers sending `decision: "reject"` without a `feedback` payload succeed validation in `validate_resume_decision()` and `services/api/presentation/schemas/rfp.py`, despite TypeScript definitions (`ResumeDecisionRequestDTO`) and JSON Schema field descriptions stating feedback is mandatory for `reject`.

## Reproduction

### Issue 1 Reproduction
1. Seed a multi-department intake ticket (e.g. `warehouse` and `lastmile`) where initial draft proposals contain conflicting constraints (e.g., volume > 50,000 vs warehouse capacity 35,000).
2. Call `RFPApprovalService.enter_approval_milestone(ticket_id)` without explicitly passing `run_initial_arbitration=True` (or via an endpoint where it defaults to `False`).
3. Department approvers review and submit `decision: "approve"`.
4. When the final department approves, `_evaluate_ticket_completion_gate()` runs `evaluate_and_arbitrate_conflicts()`.
5. The ticket is blocked from synthesis and forced back to `changes_requested` in `WAITING_FOR_APPROVAL` state, invalidating the human approval.

### Issue 2 Reproduction
1. Submit a resume decision payload with `decision: "reject"`, valid `department_id` and `approver`, but `feedback: None` or omitted.
2. In `data/pipelines/rfp_approval_completion/pipeline.py:validate_resume_decision()`, the validation passes with no error.
3. In `services/api/presentation/schemas/rfp.py:ResumeDecisionRequest`, Pydantic validation passes with no error.
4. However, `packages/shared/types/rfp.ts:ResumeDecisionRequestDTO` JSDoc explicitly reads: `/** Mandatory feedback if decision is 'request_changes' or 'reject'. */`.

## Suspected Code Paths

- `data/pipelines/rfp_approval_completion/pipeline.py:351-381` — `start_approval_phase` has parameter `run_initial_arbitration: bool = False`.
- `services/api/application/agent/rfp_approval_service.py:65-79` — `enter_approval_milestone` defaults to `run_initial_arbitration: bool = False`.
- `services/api/application/agent/rfp_approval_service.py:162-165` — `_initialize_pending_branch_checkpoints()` invokes `self.pipeline.start_approval_phase()` without `run_initial_arbitration=True`.
- `data/pipelines/rfp_approval_completion/pipeline.py:112-118` — `validate_resume_decision()` checks `if decision == "request_changes":` and does not check `decision == "reject"`.
- `services/api/presentation/schemas/rfp.py:257-265` — `ResumeDecisionRequest.validate_feedback_for_changes` only checks `if self.decision == "request_changes":`.
- `specs/033-rfp-approval-completion/contracts/resume-decision.schema.json:24-46` — property description says mandatory for `reject`, but `allOf` only checks `request_changes`.
- `packages/shared/types/rfp.ts:224-233` — JSDoc on `feedback?: string;` states `Mandatory feedback if decision is 'request_changes' or 'reject'`.

## Root Cause Hypothesis

Both issues originate from subtle specification refinements made during feature implementation:
1. `run_initial_arbitration` was originally implemented as an optional parameter (`False` by default) so unit tests could test milestone entry in isolation without invoking LLM or rule-based arbitration. However, the higher-level application service (`RFPApprovalService.enter_approval_milestone`) should default to `True` for live operations so that cross-department conflicts are arbitrated *before* department leads are asked to review drafts.
2. For resume decision validation, the functional requirement `FR-006` in `specs/033-rfp-approval-completion/spec.md` specifies:
   `"System MUST validate all incoming resume requests to ensure the decision is one of approve, reject, or request_changes, and that request_changes includes mandatory textual feedback."`
   During contract authoring, the docstring and schema description noted `request_changes or reject`, while the programmatic validator strictly enforced it only for `request_changes`.

*Confidence: High.*

## Proposed Remediation

### Preferred Solution:
1. **Initial Arbitration Default**:
   - In `services/api/application/agent/rfp_approval_service.py`: Update `enter_approval_milestone(self, ticket_id: UUID, run_initial_arbitration: bool = True)` so that live entry runs arbitration by default.
   - Also in `_initialize_pending_branch_checkpoints()`: Pass `run_initial_arbitration=True` when initializing pending branch checkpoints.
   - Maintain `run_initial_arbitration: bool = False` default in low-level `pipeline.py:start_approval_phase` to avoid breaking isolated pipeline unit test fixtures that do not seed metadata for arbitration, while allowing callers and application services to pass `run_initial_arbitration=True`.

2. **Feedback Validation Consistency**:
   - Align validators and contracts:
     - In `data/pipelines/rfp_approval_completion/pipeline.py:validate_resume_decision()`: Require non-empty feedback (min 5 chars) if `decision in ("request_changes", "reject")`.
     - In `services/api/presentation/schemas/rfp.py:ResumeDecisionRequest`: Update `validate_feedback_for_changes` (renamed to e.g. `validate_feedback_requirement`) to enforce feedback when `decision in ("request_changes", "reject")`, and update field description.
     - In `specs/033-rfp-approval-completion/contracts/resume-decision.schema.json`: Update `allOf` to enforce `feedback` when `decision` is `request_changes` OR `reject`.
   - Update tests in `tests/pipelines/test_rfp_approval_interrupts.py` to assert that rejecting without feedback raises `ResumeValidationError`.

### Alternatives:
- **Alternative for Bug 2 (Keep Reject Feedback Optional)**:
  - If operational stakeholders prefer allowing 1-click rejections without typing notes, update the JSDoc in `packages/shared/types/rfp.ts` and `resume-decision.schema.json` description to read `"Mandatory feedback if decision is 'request_changes'. Optional for 'reject'."`
  - *Trade-off*: Rejecting an enterprise RFP proposal section without providing the reason hinders traceability and director escalation. The preferred option (enforcing feedback on `reject`) provides better auditing and aligns with the existing DTO comment.

## Files Likely to Change

- `services/api/application/agent/rfp_approval_service.py`
- `data/pipelines/rfp_approval_completion/pipeline.py`
- `services/api/presentation/schemas/rfp.py`
- `specs/033-rfp-approval-completion/contracts/resume-decision.schema.json`
- `packages/shared/types/rfp.ts`
- `tests/pipelines/test_rfp_approval_interrupts.py`

## Tests to Add or Update

- `tests/pipelines/test_rfp_approval_interrupts.py`:
  - Add test asserting `validate_resume_decision` raises `ResumeValidationError` when `decision == "reject"` and `feedback` is missing or whitespace.
  - Assert that valid `decision == "reject"` with feedback >= 5 characters passes validation.
  - Verify `RFPApprovalService.enter_approval_milestone(ticket_id)` runs initial arbitration by default and records arbitration logs if conflicts exist.

## Risks & Considerations

- **Pipeline Test Suite Compatibility**: Changing the default of `pipeline.py:start_approval_phase` directly to `True` could affect isolated unit tests expecting no arbitration logs without setup; changing it at the `RFPApprovalService` layer avoids unexpected side-effects in low-level mocks.
- **Frontend / Client Submission on Reject**: Any existing frontend form submitting `decision: 'reject'` must supply a `feedback` text input. In `uis/backoffice`, review cards already provide a feedback textarea for both review actions.

## Open Questions

- None. Both bugs are well-isolated and straightforward to remediate in `/speckit-bug-fix`.
