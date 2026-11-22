# Quickstart & Validation Guide: RFP Response Generation & Department Drafting Pipeline (Part 2 of 3)

**Feature Branch**: `feature/rfp-response-generation`  
**Date**: 2026-11-22  
**Status**: Ready for Validation  
**Spec Reference**: `specs/032-rfp-response-generation/spec.md`  

---

## 1. Overview

This quickstart guide documents runnable validation scenarios that verify the implementation of **Part 2: RFP Response Generation & Department Drafting Pipeline** end-to-end.

In this workflow:
1. An RFP ticket that completed Part 1 (`analisis_completo` / `intake_complete`) is supplied.
2. The proposal drafting pipeline is triggered via REST API or CLI.
3. Dedicated generator agents draft specialized sections for active departments.
4. Parallel evaluators verify readability, relevance, and briefing compliance (§5).
5. Deficient sections iterate up to a maximum of 3 attempts (initial + 2 revisions).
6. State persists to PostgreSQL and the immutable Part 3 handoff payload is compiled.

---

## 2. Prerequisites & Environment Setup

### 2.1 Dependencies & Virtual Environment
Ensure your Python virtual environment has all necessary dependencies installed:

```powershell
cd services/api
pip install -r requirements.txt
```

Verify that `pytest`, `sqlmodel`, `langgraph`, and `textstat` are available:
```powershell
python -c "import sqlmodel, langgraph, textstat; print('Environment dependencies ready.')"
```

---

## 3. Validation Scenarios

### Scenario 1: Autonomous Proposal Generation for ModaViva Spain (Warehouse + Reverse)

**Context**: `trackflow-request-1.pdf` (ModaViva Spain: EUR currency, active departments `warehouse` and `reverse`, omitting `lastmile`).

1. **Trigger Proposal Generation**:
   ```powershell
   # Trigger proposal generation for ticket in 'analisis_completo'
   $TICKET_ID="<ticket-uuid-from-part1>"
   Invoke-RestMethod -Uri "http://localhost:8000/api/v1/rfp/$TICKET_ID/generate-proposal" -Method POST
   ```
   **Expected Response** (`202 Accepted`):
   ```json
   {
     "ticket_id": "<ticket-uuid>",
     "status": "generando_borrador",
     "message": "Proposal draft generation pipeline initiated.",
     "active_departments": ["warehouse", "reverse"]
   }
   ```

2. **Poll Generation Status**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/api/v1/rfp/$TICKET_ID/sections" -Method GET
   ```
   **Expected Outcome**:
   - `warehouse` section generated and evaluated; pricing in EUR; includes volume discount table.
   - `reverse` section generated and evaluated; return turnaround time $\ge 48$ hours; pricing in EUR.
   - `lastmile` is NOT present or marked inactive.
   - Both sections reach `passed` status within $\le 2$ iterations.

3. **Fetch Part 3 Handoff Package**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/api/v1/rfp/$TICKET_ID/part3-handoff" -Method GET
   ```
   **Expected Outcome**:
   - `overall_status`: `"passed"`
   - `department_sections`: Contains finalized draft content and passing `EvaluationResult` for `warehouse` and `reverse`.

---

### Scenario 2: Compliance Violation & Revision Feedback Loop

**Context**: Evaluator detects a return turnaround time under 48 hours or incorrect currency, triggering automated revision.

1. **Simulate Section Draft with Rule Violation**:
   - A draft promising `24-hour return inspection` is evaluated.
   - Evaluator flags `RULE-RETURNS-TIME`: `compliance.pass == false`, `overall_pass == false`.
   - `feedback_for_generator`: "Violates RULE-RETURNS-TIME: TrackFlow policy prohibits promising returns turnaround under 48 hours. Please update to at least 48-72 hours."

2. **Automated Feedback Loop**:
   - Section re-enters `generando_borrador` with `iteration = 2`.
   - Generator agent incorporates feedback and updates turnaround to 48 hours.
   - Re-evaluator scores `compliance.pass == true`, `overall_pass == true`.
   - Loop exits cleanly; status updates to `passed`.

---

### Scenario 3: Iteration Cap Exhaustion & Graceful Escalation to `needs_human_review`

**Context**: A section fails compliance after exhausting 3 attempts (max 2 revisions).

1. **Execute Mock Test Fixture**:
   ```powershell
   pytest services/api/tests/unit/agent/ -k "test_rfp_iteration_cap" -v
   # or run the dedicated pipeline test:
   pytest tests/pipelines/test_rfp_response_generation.py -v
   ```

2. **Expected Behavior**:
   - Generator produces draft attempt 1 (fails).
   - Generator produces draft attempt 2 (fails).
   - Generator produces draft attempt 3 (fails).
   - Feedback loop terminates immediately after attempt 3.
   - Section status transitions to `needs_human_review`.
   - Ticket status transitions to `needs_human_review` (NOT `descartado`).
   - Latest draft and `EvaluationResult` with violated rule citations are fully retained.
   - Part 3 handoff payload is emitted with `overall_status: "needs_human_review"`.

---

## 4. Automated Verification Commands

Run the full pipeline test suite verifying all acceptance criteria:

```powershell
# 1. Pipeline Unit Tests (Department generators, evaluators, compliance rules)
pytest tests/pipelines/test_rfp_response_generation.py -v

# 2. RFP Agent Unit Tests
pytest services/api/tests/unit/agent/ -v

# 3. Integration & Contract Tests
pytest services/api/tests/integration/test_rfp_generation_api.py -v
```

All tests must pass with zero errors, zero unhandled warnings, and zero database locks.
