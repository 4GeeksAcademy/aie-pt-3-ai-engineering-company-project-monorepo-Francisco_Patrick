# Quickstart Validation Guide: RFP Intake & Agentic Analysis Pipeline

**Feature Branch**: `031-rfp-intake`  
**Date**: 2026-11-21  
**Status**: Completed  
**Spec Reference**: `specs/031-rfp-intake/spec.md`

---

## 1. Overview & Prerequisites

This quickstart guides developers and QA engineers through end-to-end validation of the RFP Intake & Agentic Analysis Pipeline (Part 1).

### Prerequisites
- Python 3.12+ (or 3.14 per monorepo setup) with virtual environment in `services/api/.venv/`
- Node.js 20+ with npm dependencies installed in `uis/backoffice/`
- Running API server (`uvicorn main:app --reload` on port 8000) or test execution environment

---

## 2. Automated Test Suite Execution

Run all unit, integration, and contract tests for the RFP pipeline:

```bash
# From services/api/
pytest tests/unit/agent/test_rfp_classifier.py \
       tests/unit/agent/test_rfp_orchestrator.py \
       tests/unit/agent/test_rfp_department_workers.py \
       tests/unit/agent/test_rfp_synthesizer.py \
       tests/integration/test_rfp_intake_api.py -v
```

---

## 3. End-to-End Validation Scenarios

### Scenario 1: Carrier Rate Pitch Rejection (Non-RFP)

**Objective**: Verify that inbound carrier pitches and vendor solicitations are rejected immediately without invoking department workers.

1. **Submit File via CLI**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/rfp/intake" \
     -H "Accept: application/json" \
     -F "file=@docs/agentic-workflows/rfp-requests/trackflow-request-3.pdf"
   ```

2. **Expected Initial Response** (`HTTP 202 Accepted` in <500ms):
   ```json
   {
     "ticket_id": "c1f7b889-1234-4a21-99ef-8a9d0f4d3201",
     "ticket_number": "RFP-2026-001",
     "status": "analizando",
     "message": "Proposal accepted for analysis. Processing in background.",
     "created_at": "2026-11-21T14:30:00Z"
   }
   ```

3. **Poll Ticket Status**:
   ```bash
   curl "http://localhost:8000/api/v1/rfp/tickets/c1f7b889-1234-4a21-99ef-8a9d0f4d3201"
   ```

4. **Expected Terminal Outcome**:
   - `status`: `"descartado"` (or `"discarded"`)
   - `rejection_reason`: Contains clear message indicating document is a carrier rate pitch from RapidShip Carriers soliciting TrackFlow, not a customer RFP.
   - `department_sections`: Empty (`[]`).
   - `handoff`: `null`.

---

### Scenario 2: Valid Spain RFP Ingestion & Department Scoping (ModaViva)

**Objective**: Verify document parsing, readability calculation, department scoping (Warehouse + Reverse Logistics; Last Mile omitted), and open questions capture.

1. **Submit File**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/rfp/intake" \
     -F "file=@docs/agentic-workflows/rfp-requests/trackflow-request-1.pdf"
   ```

2. **Poll Ticket Status** until status becomes `analisis_completo`:
   ```bash
   curl "http://localhost:8000/api/v1/rfp/tickets/<TICKET_ID>"
   ```

3. **Expected Outcomes**:
   - `status`: `"analisis_completo"`
   - `metadata.client_name`: `"ModaViva, S.L."`
   - `metadata.client_country`: `"ES"`
   - `metadata.currency`: `"EUR"`
   - `metadata.departments_needed`: `["warehouse", "reverse"]` (Strictly excludes `"lastmile"`)
   - `metadata.readability_scores.flesch_reading_ease`: Calculated valid float (e.g. 50-70)
   - `department_sections`:
     - Contains `warehouse` section with responsible person `Ana Whitfield`. Missing pallet specifications are captured in `open_questions` (Zero Hallucination).
     - Contains `reverse` section with responsible person `Sofía Ramos` noting 30-day standard return window and inspection flow.
     - Does **NOT** contain `lastmile` section.
   - `handoff`: Present and populated according to `contracts/handoff-payload-schema.json`.

---

### Scenario 3: Valid US RFP Ingestion & Volume Extraction (Luna Cosmetics)

**Objective**: Verify United States operating country, USD currency, volume extraction, and department scoping (Warehouse + Last Mile).

1. **Submit File**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/rfp/intake" \
     -F "file=@docs/agentic-workflows/rfp-requests/trackflow-request-2.pdf"
   ```

2. **Expected Verification**:
   - `metadata.client_name`: `"Luna Cosmetics"`
   - `metadata.client_country`: `"US"`
   - `metadata.currency`: `"USD"`
   - `metadata.monthly_volume`: `5000`
   - `metadata.departments_needed`: `["warehouse", "lastmile"]`
   - `department_sections`:
     - `warehouse` (Ana Whitfield): Notes LA garage transition, monthly volume 5,000 orders.
     - `lastmile` (Carlos Vega): Notes domestic US delivery across US states.

---

### Scenario 4: Corrupted / Non-PDF Upload Guardrail

**Objective**: Verify defensive handling of unreadable or corrupted files.

1. **Submit Text / Corrupt File**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/rfp/intake" \
     -F "file=@README.md"
   ```

2. **Expected Outcome**:
   - Immediate HTTP 400 Bad Request with sanitized message: `"Invalid file type: only PDF documents (.pdf) are supported."`
   - No orphan tickets created.

---

### Scenario 5: Handoff Payload Retrieval for Part 2

**Objective**: Verify the Part 2 proposal generation endpoint retrieves the canonical handoff bundle.

1. **Fetch Handoff**:
   ```bash
   curl "http://localhost:8000/api/v1/rfp/tickets/<COMPLETED_TICKET_ID>/handoff"
   ```

2. **Expected Outcome**:
   - `HTTP 200 OK`
   - Valid JSON matching `contracts/handoff-payload-schema.json` with `schema_version: "1.0.0"`.

---

## 4. Backoffice UI Verification

1. Navigate to `http://localhost:3000/rfp` in `uis/backoffice`.
2. Drag and drop `trackflow-request-1.pdf`.
3. Confirm instantaneous display of ticket row with pulsing `"analizando"` status badge.
4. Observe automatic status transition to `"analisis_completo"` within 5-10 seconds.
5. Click ticket row to open detail view:
   - Verify readability score widget (Flesch Reading Ease and Grade Level).
   - Verify Warehouse and Reverse tabs are present; Last Mile tab is absent.
   - Confirm open questions are clearly listed without fabricated pallet numbers.
