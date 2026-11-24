# Feature Specification: RFP Intake & Agentic Analysis Pipeline (Part 1 of 3)

**Feature Branch**: `feature/rfp-intake`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "RFP Intake & Agentic Analysis Pipeline — Implement async ticket-mode intake & storage in PostgreSQL for PDF RFPs via uis/backoffice, pre-agent markdown conversion (MarkItDown) and readability metric calculation, classifier agent for RFP validity, dedicated rfp_intake orchestrator-worker-synthesizer pipeline with department scoping (warehouse, lastmile, reverse) per trackflow-BRIEFING.es.md, key aspects extraction without fabrication, synthesis report for Sales, and Part 2 handoff payload."

## Clarifications & Design Decisions

### Session 2026-11-21

- **Q1: Unknown Departments**: How do the classifier and orchestrator handle an RFP referencing services or departments not listed in `trackflow-BRIEFING.es.md` (e.g., customs clearance, air freight, cold storage)?
  - **Resolution**: TrackFlow operates strictly with three fulfillment departments: `warehouse` (Ana Whitfield), `lastmile` (Carlos Vega), and `reverse` (Sofía Ramos). Any requested services outside these three are cataloged as "unsupported_services" in RFP metadata and surfaced as open business questions in the Sales synthesis report, while only the recognized departments are assigned worker runs.
- **Q2: State Scoping & Missing Data**: What exact slice of state does each department worker receive, and how are missing figures handled?
  - **Resolution**: Workers receive shared RFP metadata plus filtered Markdown extracts relevant to their domain. Workers are strictly forbidden from hallucinating or inventing missing volumes, pallet counts, or delivery SLAs; missing information must be explicitly captured as structured items under `key_aspects.open_questions`.
- **Q3: Classification Thresholds & False Negatives**: What defines "not an RFP", and how are non-RFPs handled?
  - **Resolution**: An RFP is valid if and only if an inbound prospective or existing client is soliciting fulfillment, warehousing, shipping, or returns services from TrackFlow. Inbound carrier rate pitches (e.g., transport vendor sales sheets), supplier material invoices, marketing brochures, and spam are classified as non-RFPs. Non-RFPs stop execution cleanly, updating ticket status to `descartado` (discarded) with an explicit human-readable rejection reason logged.
- **Q4: Worker Contradictions**: How are conflicting claims across department workers resolved or flagged during synthesis?
  - **Resolution**: The synthesizer node evaluates structured cross-department claims against TrackFlow policy rules (e.g., monthly volume exceeding warehouse onboarding capacity, reverse logistics turnaround promised under 48 hours, or currency mismatch between US and Spain). The synthesizer surfaces any policy violations or conflicting claims as `flagged_contradictions` in the Sales report so commercial management (Miguel Torres) can arbitrate prior to proposal drafting in Part 2.
- **Q5: Async Execution & Crash Recovery**: Where does background execution run, and how is ticket state preserved during unexpected failures?
  - **Resolution**: PDF uploads return HTTP 202 immediately with a unique `ticket_id` and initial status `analizando` (analyzing). The pipeline executes asynchronously via backend background tasks. All pipeline stages run within transactional try-except boundaries: any mid-pipeline unhandled exception or agent failure updates the ticket status to `descartado` (or explicit failure state) and persists error diagnostics, preventing tickets from becoming orphaned in an indefinite `analizando` state.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Asynchronous Ingestion & Document Validity Screening (Priority: P1)

As a TrackFlow Commercial Account Manager (reporting to Miguel Torres, Commercial Director),  
I want to upload incoming client PDF proposals through the backoffice interface and immediately receive a tracked ticket,  
So that large documents are ingested without browser timeouts, and invalid submissions (such as carrier rate pitches or spam) are discarded automatically with transparent reasons.

**Why this priority**:
Reliable, non-blocking ingestion and rapid rejection of non-RFP documents prevents commercial team members from wasting time manually reviewing irrelevant vendor solicitations and guarantees system availability.

**Independent Test**:
Can be tested independently by uploading `trackflow-request-3.pdf` (carrier pitch) via the backoffice UI or intake endpoint: the system returns an immediate acceptance ticket (`202 Accepted`), transitions to `analizando`, and terminates at the classifier agent with final status `descartado` and a clear rejection reason in the ticket record.

**Acceptance Scenarios**:

1. **Given** a user uploads a valid or invalid PDF document via the backoffice intake form,  
   **When** the upload request reaches the backend API,  
   **Then** the raw PDF is stored in persistent storage (`data/raw/`), an intake ticket is created with status `analizando`, and the endpoint responds immediately with HTTP 202 and the `ticket_id`.
2. **Given** an uploaded document that is not a customer RFP (e.g., transport carrier price list or vendor marketing brochure),  
   **When** the classifier agent evaluates the converted document text,  
   **Then** the classifier flags the document as invalid, stops further pipeline execution, and marks the ticket status as `descartado` with an explicit reason.
3. **Given** an uploaded document that is corrupted or unreadable,  
   **When** the ingestion engine attempts conversion,  
   **Then** the failure is captured gracefully without crashing the service, and the ticket status is updated to `descartado` with diagnostic error logging.

---

### User Story 2 - Automated RFP Analysis, Metadata Extraction & Department Scoping (Priority: P2)

As an Account Manager,  
I want valid customer RFPs to be parsed into structured operational metadata (client name, operating country, monthly order volume, deadline, budget) and routed only to the departments relevant to the client's requested scope,  
So that our operations leaders (Warehouse, Last Mile, Reverse Logistics) receive clear, relevant briefs without manual document slicing.

**Why this priority**:
Accurate department scoping ensures that internal teams only analyze services requested by the client (e.g., excluding Last Mile when the client uses their own carrier), cutting response turnaround time from days to minutes.

**Independent Test**:
Can be tested independently using `trackflow-request-1.pdf` (ModaViva Spain): verify that the orchestrator extracts country as Spain (EUR currency), requested services as warehousing and returns, and invokes only the `warehouse` and `reverse` department workers (bypassing `lastmile`).

**Acceptance Scenarios**:

1. **Given** a valid client RFP from Spain requesting storage and returns with self-managed carrier delivery,  
   **When** the orchestrator runs the department scoping logic,  
   **Then** `warehouse` and `reverse` workers are activated, while `lastmile` is omitted from the ticket's active departments.
2. **Given** an informal client RFP email from the United States requesting storage and delivery of ~5,000 orders/month,  
   **When** the orchestrator processes the document,  
   **Then** `warehouse` and `lastmile` workers are activated, operating currency is set to USD, and estimated monthly volume is recorded as 5,000.
3. **Given** an RFP that omits explicit pallet counts or storage dimensions,  
   **When** the `warehouse` worker evaluates its assigned extract,  
   **Then** the worker records pallet requirements as unknown and appends an explicit clarifying question to `key_aspects.open_questions` rather than guessing or fabricating numbers.

---

### User Story 3 - Synthesis Report & Part 2 Handoff Generation (Priority: P3)

As Miguel Torres (Commercial Director) or an Account Manager preparing a quotation,  
I want a consolidated executive synthesis of key operational aspects, identified risks, missing client data, and recommended contacts,  
So that I can immediately review proposal readiness and hand off the structured analysis to proposal drafting (Part 2) without re-parsing the original document.

**Why this priority**:
The synthesis report is the primary user-facing deliverable of Part 1. It bridges operational department analyses into actionable commercial insights and establishes the canonical data handoff payload for drafting (Part 2) and approvals (Part 3).

**Independent Test**:
Can be tested independently by querying the ticket status for a completed RFP: verify that the ticket status is `analisis_completo`, all active department `key_aspects` are persisted, the synthesis summary highlights open questions and contacts, and the handoff payload contains the structured contract required for Part 2.

**Acceptance Scenarios**:

1. **Given** all active department workers have completed their individual analyses,  
   **When** the synthesizer agent executes,  
   **Then** the synthesizer aggregates department findings, cross-checks for policy conflicts (e.g., return turnaround times under 48 hours or volume capacity mismatches), and produces an executive summary for Sales.
2. **Given** a completed synthesis,  
   **When** the pipeline finalizes the ticket,  
   **Then** ticket status updates to `analisis_completo` (or `intake_complete`), and a documented handoff payload containing `ticket_id`, RFP metadata, department `key_aspects`, and the executive synthesis is persisted.
3. **Given** an Account Manager viewing the backoffice proposal intake dashboard,  
   **When** polling or viewing the completed ticket,  
   **Then** the UI displays the executive summary, active departments, readability scores, and identified clarification items.

---

### Edge Cases

- **Corrupted or Password-Protected PDFs**: If a user uploads an encrypted or unreadable PDF, MarkItDown or conversion fails; the system marks the ticket `descartado` with an error message "PDF conversion failed: file unreadable or password-protected" without raising an unhandled 500 error.
- **RFP Requesting Unsupported Services**: When a prospective client requests freight forwarding, customs clearance, or refrigeration alongside standard fulfillment, the orchestrator classifies these as unsupported services and flags them in the Sales synthesis report while routing standard storage/delivery to existing departments.
- **Contradictory or Incomplete Customer Data**: When an RFP states conflicting volume numbers (e.g., "5,000 orders/month in text, but 12,000 in appendix table"), workers flag the variance in `key_aspects.open_questions` rather than picking one arbitrarily.
- **Mid-Pipeline Execution Crash**: If an agent service or LLM provider times out during department analysis, the top-level exception handler catches the failure, records the error on the ticket, and updates status to `descartado` (or explicit failure state), allowing operators to reprocess the ticket cleanly without orphan locks.
- **Multiple Concurrent Ingestions**: Multiple simultaneous PDF uploads process independently through separate tickets and persistent records without race conditions or shared state contamination.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an intake endpoint and backoffice UI view allowing users to upload PDF RFP documents and receive an immediate HTTP 202 response with a unique `ticket_id` and status `analizando`.
- **FR-002**: The system MUST store uploaded raw PDF files in persistent disk storage under `data/raw/` preserving traceable filenames linked to the `ticket_id`.
- **FR-003**: The system MUST convert the raw PDF into standard Markdown representation prior to passing content to any LLM agent.
- **FR-004**: The system MUST compute document readability and complexity metrics (including reading grade level and reading ease scores) from the converted Markdown and persist them within the ticket metadata in PostgreSQL.
- **FR-005**: The system MUST evaluate the converted Markdown with a dedicated Classifier Agent to determine whether the document represents a genuine customer proposal request (RFP).
- **FR-006**: When a document is classified as a non-RFP (e.g., carrier rate pitch, supplier invoice, spam), the system MUST terminate the pipeline cleanly and transition the ticket status to `descartado` with a documented rejection explanation.
- **FR-007**: When an RFP is confirmed valid, the system MUST execute a dedicated `rfp_intake` orchestrator pipeline that extracts standardized RFP metadata (`client_name`, `client_country`, `currency`, `services_requested`, `monthly_volume`, `deadline`, `budget_range`, `departments_needed`).
- **FR-008**: The orchestrator MUST route work only to operational departments identified in `trackflow-BRIEFING.es.md`: `warehouse` (Warehouse Operations, Ana Whitfield), `lastmile` (Last Mile & Carrier Management, Carlos Vega), and `reverse` (Reverse Logistics, Sofía Ramos), omitting unneeded departments.
- **FR-009**: Department workers MUST receive structured metadata and domain-relevant document extracts; workers MUST NOT fabricate missing figures (e.g., pallet dimensions, SLA commitments, volume tiers) and MUST record missing or uncertain data under `key_aspects.open_questions`.
- **FR-010**: The system MUST persist department analysis results (`key_aspects`) into PostgreSQL (Supabase) via the existing SQLModel persistence architecture.
- **FR-011**: The system MUST run a Synthesizer Agent that consolidates department analyses, highlights cross-department contradictions or policy infractions (e.g., returns turnaround promises under 48 hours, volume exceeding warehouse onboarding capacity), and drafts a commercial executive summary for Sales.
- **FR-012**: Upon successful synthesis, the system MUST update the ticket status to `analisis_completo` (intake_complete) and emit a structured, versioned handoff payload (`ticket_id`, metadata, readability metrics, per-department `key_aspects`, executive synthesis) allowing proposal generation (Part 2) to execute without re-parsing the original PDF.
- **FR-013**: The backoffice UI in `uis/backoffice` MUST provide an upload interface and ticket status view that polls or refreshes ticket progression (`analizando` -> `analisis_completo` / `descartado`) and displays key findings and open questions.
- **FR-014**: The system MUST isolate pipeline failures so that a crashed or rejected ticket does not block subsequent ticket processing and guarantees truthful status tracking in PostgreSQL.

### Key Entities

- **IntakeTicket**:
  - Represents the lifecycle of an uploaded proposal document.
  - Attributes: `ticket_id` (UUID/string), `status` (`analizando`, `descartado`, `analisis_completo`), `raw_pdf_path` (string), `error_message` (optional string), `created_at` (timestamp), `updated_at` (timestamp).
- **RFPMetadata**:
  - Standardized business information extracted from the RFP.
  - Attributes: `ticket_id` (foreign key), `client_name` (string), `client_country` (`US` | `ES`), `currency` (`USD` | `EUR`), `services_requested` (list of strings), `monthly_volume` (optional integer), `deadline` (optional string), `budget_range` (optional string), `departments_needed` (list of strings: `warehouse`, `lastmile`, `reverse`), `readability_metrics` (JSON object containing Flesch Reading Ease, Flesch-Kincaid Grade, etc.).
- **DepartmentSection**:
  - Structured operational assessment per active department.
  - Attributes: `id` (primary key), `ticket_id` (foreign key), `department_id` (`warehouse` | `lastmile` | `reverse`), `responsible_person` (string: Ana Whitfield, Carlos Vega, or Sofía Ramos), `key_aspects` (JSON object including operational requirements, cost drivers, assumptions, and open questions), `created_at` (timestamp).
- **IntakeHandoffPayload**:
  - The immutable handover artifact emitted upon intake completion.
  - Attributes: `ticket_id`, `metadata` (RFPMetadata), `department_aspects` (map of department_id to key_aspects), `sales_synthesis` (executive summary, key questions to ask the prospect, relevant internal contacts, flagged contradictions).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ingestion API endpoint acknowledges PDF uploads within 500ms by returning HTTP 202 and `ticket_id`, never blocking the client thread on agent processing.
- **SC-002**: 100% of non-RFP documents (including vendor pitch PDFs like `trackflow-request-3.pdf`) are accurately rejected and transitioned to `descartado` without triggering downstream department workers.
- **SC-003**: 100% of valid RFP documents (such as `trackflow-request-1.pdf` and `trackflow-request-2.pdf`) are successfully processed to `analisis_completo` with complete metadata and department scoping matching the requested services.
- **SC-004**: Department workers produce zero fabricated figures; 100% of missing critical parameters (e.g., unknown volume, missing pallet specs) are recorded as explicit open questions in the `key_aspects` payload.
- **SC-005**: All ticket lifecycle states, extracted RFP metadata, readability metrics, and per-department `key_aspects` are persistently queryable in PostgreSQL (Supabase) via SQLModel.
- **SC-006**: Backoffice UI displays real-time ticket progression from `analizando` to completion or rejection within 3 seconds of state change.
- **SC-007**: Automated test suite achieves 100% passing rate across pipeline unit tests (classifier agent, department workers, orchestrator routing) with zero regression in monorepo builds.

## Assumptions

- **Target Operating Countries**: In accordance with `trackflow-BRIEFING.es.md`, TrackFlow operates fulfillment services in the United States (`US`, currency `USD`) and Spain (`ES`, currency `EUR`). Client country deterministically fixes the commercial currency.
- **Department Universe**: Only three departments participate in operational RFP intake: Warehouse Operations (`warehouse`), Last Mile & Carrier Management (`lastmile`), and Reverse Logistics (`reverse`).
- **Tooling Stack**: Markdown conversion is performed using `markitdown` (or documented Python parser), and readability metrics are calculated via `py-readability-metrics`.
- **Database Architecture**: Persistence strictly uses the existing SQLModel / PostgreSQL (Supabase) backend adapter stack in `services/api/infrastructure/persistence/`, upholding Constitution Principle I (Service Boundaries) and Principle II (Contract Serialization).
- **Status Terminology Alignment**: The internal pipeline supports both English and Spanish status vocabulary aliases (`analyzing` / `analizando`, `discarded` / `descartado`, `intake_complete` / `analisis_completo`) with canonical persistence matching the briefing specification.
- **Scope Boundary (Part 1 vs Parts 2 & 3)**: Part 1 delivers document ingestion, classification, metadata extraction, department worker analysis (`key_aspects`), sales synthesis, and the routing handoff payload. Section drafting, parallel evaluation loops, human approval pauses (`esperando_aprobación`), and final document rendering belong to subsequent milestones (Parts 2 and 3).
