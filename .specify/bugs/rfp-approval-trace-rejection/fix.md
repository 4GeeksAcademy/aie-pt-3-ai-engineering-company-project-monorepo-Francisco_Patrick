# Bug Fix: RFP Approval Completion Traces, Rejection Lifecycle & Canonical Values

- **Slug**: rfp-approval-trace-rejection
- **Fixed**: 2026-11-23T17:49:50+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Wired `arbitration_node` and consolidated execution traces across `arbitration_node` and `final_synthesis_node` in `RFPApprovalCompletionPipeline`. Transitioned rejected department tickets to `needs_human_review` under Commercial Director Miguel Torres with commercial reopening support, and aligned all Part 3 test fixtures and UI mocks with canonical BRIEFING values (90% SLA and 16.00 EUR por m³ in Zaragoza).

## Changes

| File | Change | Notes |
|------|--------|-------|
| `data/pipelines/rfp_approval_completion/pipeline.py` | modified | Replaced direct calls with traced `arbitration_node`, propagated gate traces (`arbitration_node` + `final_synthesis_node`) to `resume_department_approval`, escalated `rejected` branches to `needs_human_review`, added commercial reopening handling for previously rejected branches, and corrected obsolete import from `application.agent`. |
| `data/pipelines/rfp_intake/rfp_approval_service.py` | modified | Allowed resumption of `rejected` branches when valid reopening action (`request_changes` or `approve`) is supplied. |
| `tests/pipelines/test_rfp_approval_interrupts.py` | modified | Corrected imports to `data.pipelines.rfp_intake`, replaced obsolete 99.2% SLA with canonical 90% SLA, and added `test_rejection_lifecycle_and_commercial_reopening`. |
| `tests/pipelines/test_rfp_arbitration.py` | modified | Corrected imports to `data.pipelines.rfp_intake` and sanitized non-canonical rates (`16.50 EUR per pallet` -> `16.00 EUR por m³`, `99.2% SLA` -> `90% SLA`). |
| `tests/pipelines/test_rfp_final_synthesis.py` | modified | Corrected imports, sanitized non-canonical rates and SLAs, added verification for canonical values in synthesized `FinalDocument`, and asserted execution traces for `arbitration_node` and `final_synthesis_node`. |
| `tests/pipelines/test_rfp_e2e_complete.py` | modified | Corrected imports from `application.agent.*` to `data.pipelines.rfp_intake.*`. |
| `uis/backoffice/__tests__/DepartmentApprovalPanel.test.tsx` | modified | Replaced non-canonical draft rate (`16.50 EUR per pallet` -> `16.00 EUR por m³`). |

## Diff Highlights

```python
# data/pipelines/rfp_approval_completion/pipeline.py
# Rejection escalation & preventing zombie waiting state
if rejected_depts:
    first_rejected = rejected_depts[0]
    feedback = (
        sections.get(first_rejected, {}).get("review_feedback")
        or "Department rejected proposal."
    )
    err_msg = (
        f"Escalated to {COMMERCIAL_DIRECTOR} (Commercial Director): "
        f"department '{first_rejected}' rejected proposal: {feedback}"
    )
    if self.repository is not None:
        ticket = self.repository.get_ticket(ticket_id)
        if ticket is not None:
            ticket.mark_needs_human_review(error_message=err_msg)
            self.repository.save_ticket(ticket)
    return TicketStatus.NEEDS_HUMAN_REVIEW.value, None, []

# Wiring traced nodes and consolidating traces
arb_state = arbitration_node({
    "ticket_id": str(ticket_id),
    "rfp_metadata": meta,
    "department_sections": sections,
    "max_revisions": self.max_revisions,
    "arbitration_logs": [],
    "execution_trace": [],
})
gate_traces.extend(arb_state.get("execution_trace") or [])
...
synth_state = final_synthesis_node({
    "ticket_id": str(ticket_id),
    "rfp_metadata": updated_meta,
    "department_sections": updated_sections,
    "active_departments": active_departments,
    "execution_trace": gate_traces,
})
gate_traces = list(synth_state.get("execution_trace") or [])
```

## Tests Added or Updated

- `tests/pipelines/test_rfp_approval_interrupts.py::test_rejection_lifecycle_and_commercial_reopening` — verifies that department rejection immediately transitions ticket out of `esperando_aprobación` into `needs_human_review`, prevents blind repeat resumes, and allows commercial reopening via `request_changes` and `approve`.
- `tests/pipelines/test_rfp_final_synthesis.py::test_execution_trace_recording_across_nodes` — verifies that `execution_trace` explicitly records `arbitration_node` and `final_synthesis_node` with input and output snapshots.
- `tests/pipelines/test_rfp_final_synthesis.py::test_complete_approval_milestone_transitions_ticket_to_terminado` — verifies that the final document generated reflects canonical values (90% SLA and 16.00 EUR por m³) without obsolete Part 2 values.

## Local Verification

- Commands run:
  - `services/api/.venv/Scripts/python.exe -m pytest tests/pipelines/test_rfp_approval_interrupts.py tests/pipelines/test_rfp_arbitration.py tests/pipelines/test_rfp_final_synthesis.py tests/pipelines/test_rfp_e2e_complete.py tests/pipelines/test_rfp_compliance_failures.py tests/pipelines/test_rfp_evaluators.py -v` → 21 passed in 4.97s.
  - `cmd.exe /c "cd uis\backoffice && npm test -- DepartmentApprovalPanel"` → 1 passed, 3 tests passed in 1.199s.
  - `cmd.exe /c "cd uis\backoffice && npm run typecheck"` → exited with code 0 (clean compilation).

## Deviations from Assessment

None. All preferred remediations were implemented exactly as specified in `assessment.md`.

## Follow-ups

- Continue verification with `/speckit-bug-test slug=rfp-approval-trace-rejection`.
