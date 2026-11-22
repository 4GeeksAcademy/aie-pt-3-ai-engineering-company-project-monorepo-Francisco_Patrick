# Quickstart & Verification Guide: RFP Approval, Arbitration & Document Synthesis (Part 3 of 3)

**Branch**: `033-rfp-approval-completion` | **Date**: 2026-11-22 | **Spec**: [specs/033-rfp-approval-completion/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/033-rfp-approval-completion/spec.md)

---

## 1. Prerequisites & Environment Setup

Ensure the virtual environment is active and dependencies are installed:

```bash
# From repository root
cd services/api
# Ensure required python dependencies are available
python -m pip install -r requirements.txt
```

Verify backend and shared packages:
```bash
# TypeScript workspace type integrity check
npm run typecheck
```

---

## 2. Test Execution Commands

### 2.1 Automated Unit & Pipeline Tests
Run the dedicated test suite for Part 3 approvals, arbitration triggers, and synthesis:

```bash
# Run all RFP Part 3 pipeline unit tests
pytest tests/pipelines/test_rfp_approval_interrupts.py -v
pytest tests/pipelines/test_rfp_arbitration.py -v
pytest tests/pipelines/test_rfp_final_synthesis.py -v
```

### 2.2 End-to-End Complete Handoff Test
Execute the continuous E2E test running Part 1 intake -> Part 2 drafting -> Part 3 approval & synthesis:

```bash
pytest tests/pipelines/test_rfp_e2e_complete.py -v
```

---

## 3. Step-by-Step Validation Scenarios

### Scenario 1: Scoped Interruption & Parallel Branch Independence (AC-1.1, AC-1.2)
1. **Goal**: Verify that approving Department A (`lastmile`, Carlos Vega) advances that branch to `approved` while Department B (`warehouse`, Ana Whitfield) remains paused in its scoped interruption.
2. **Setup**:
   - Initialize a multi-department ticket with `active_departments: ["warehouse", "lastmile"]`.
   - Execute Part 3 pipeline up to the review checkpoints.
3. **Execution**:
   - Check graph state: both branches are in `interrupted` status.
   - Post resume call for `lastmile` with `{"decision": "approve", "approver": "Carlos Vega"}`.
4. **Expected Outcome**:
   - HTTP 200 returned.
   - `lastmile` section in PostgreSQL shows `approval_status = "approved"` and `approved_at` is set.
   - `warehouse` section remains `approval_status = "pending"`.
   - Ticket status remains `esperando_aprobación`.
   - Final document synthesis is **not** triggered.

---

### Scenario 2: Deterministic Conflict Arbitration (AC-2.2)
1. **Goal**: Verify that structured contradictions trigger deterministic resolution under named arbiters without LLM debate.
2. **Execution & Outcomes**:
   - **Trigger 1 (`volume-vs-capacity`)**:
     - *State*: Warehouse capacity is 3,000 orders/mo; Last Mile volume is 5,000 orders/mo.
     - *Result*: `ArbitrationNode` creates an `ArbitrationLog` record under arbiter **Miguel Torres**, caps proposal volume at 3,000, and flags `lastmile` for downward revision.
   - **Trigger 2 (`returns-sla-breach`)**:
     - *State*: Reverse section promises 24-hour return turnaround.
     - *Result*: `ArbitrationNode` triggers `returns-sla-breach`, arbiter **Sofía Ramos** / **Miguel Torres** forces `request_changes`, and blocks final synthesis.
   - **Trigger 3 (`currency-mismatch`)**:
     - *State*: Spanish client (`client_country: "ES"`) quoted in `USD`.
     - *Result*: `ArbitrationNode` triggers `currency-mismatch`, arbiter **Miguel Torres** rewrites figures to `EUR`.

---

### Scenario 3: Iteration Cap & Graceful Escalation (AC-2.1)
1. **Goal**: Verify that revision loops terminate deterministically after 2 revisions without infinite looping or ticket discarding.
2. **Execution**:
   - Approver submits `request_changes` with feedback 2 consecutive times (`iteration_count` increments from 0 to 1, then 1 to 2).
   - On the 3rd attempt, if changes remain unapproved, the workflow halts.
3. **Expected Outcome**:
   - Loop terminates deterministically.
   - Section status transitions to `needs_human_review` / escalated.
   - An escalation note is addressed to Miguel Torres (Commercial Director).
   - Ticket is **never** discarded (`descartado`).

---

### Scenario 4: Automatic Final Document Synthesis & Completion (AC-3.2, AC-3.3)
1. **Goal**: Verify that final proposal document is generated automatically once all active departments approve, completing the ticket.
2. **Execution**:
   - Resume remaining pending department (`warehouse`, Ana Whitfield) with `{"decision": "approve", "approver": "Ana Whitfield"}`.
3. **Expected Outcome**:
   - 100% of active department sections are now `approved`.
   - `FinalSynthesisNode` triggers automatically.
   - `FinalDocument` row is persisted in PostgreSQL with client profile, currency (`EUR` or `USD`), executive summary, and consolidated approved sections.
   - Ticket status transitions to `terminado` (`done`).
