# Research: RFP Intake & Agentic Analysis Pipeline (Part 1 of 3)

**Feature Branch**: `031-rfp-intake`  
**Date**: 2026-11-21  
**Status**: Completed  
**Spec Reference**: `specs/031-rfp-intake/spec.md`

---

## 1. Document Ingestion & Markdown Conversion

### Background & Needs
TrackFlow commercial account managers receive customer proposals and RFP requests as PDF documents. Prior to passing text content to LLM agents (Classifier, Orchestrator, Department Workers, Synthesizer), the raw PDF must be converted to standard Markdown.

### Decision
Implement a decoupled converter architecture with a domain port `DocumentConverterPort` and an infrastructure adapter `PdfToMarkdownAdapter`.
- The adapter primarily leverages `pypdf` for resilient, zero-native-dependency text extraction and structured Markdown formatting (preserving section headers, itemized lists, tables, and metadata blocks).
- Pluggable fallback or delegation to `markitdown` is supported, but guarded against runtime DLL load failures.

### Rationale
- During environment testing on Windows, `markitdown` imports `magika`, which imports `onnxruntime`, causing `ImportError: DLL load failed while importing onnxruntime_pybind11_state` when specific Microsoft Visual C++ runtime redistributables are absent.
- `pypdf` (v7.1.1) is pure Python, operates without external system binaries, executes in <10ms for multi-page documents, and reliably extracts clean text streams for `trackflow-request-1.pdf`, `trackflow-request-2.pdf`, and `trackflow-request-3.pdf`.
- Clean Markdown formatting ensures agents receive structured headings (`#`, `##`, `-`) rather than unformatted byte blobs.

### Alternatives Considered
- **Direct unmanaged `markitdown`**: Fails on environments lacking MSVC++ runtimes for ONNX.
- **`pymupdf` (fitz)**: AGPL licensing restrictions and C-extension compilation requirements.
- **`pdfplumber`**: Slower for standard text-based RFP extraction.

---

## 2. Readability & Complexity Metric Calculation

### Background & Needs
FR-004 requires computing document readability metrics (including reading grade level and reading ease scores) from the converted Markdown and persisting them within the ticket metadata in PostgreSQL.

### Decision
Implement `ReadabilityCalculatorPort` with `TextstatReadabilityAdapter` (using `textstat` v0.7.13), returning a normalized `ReadabilityMetrics` value object.
Metrics calculated:
- `flesch_reading_ease` (0 - 100, where higher is easier)
- `flesch_kincaid_grade` (US school grade level)
- `reading_level_label` (e.g., "Standard", "Difficult", "Very Confusing")
- `word_count` (total token/word count)
- `sentence_count` (total sentences)

### Rationale
- `py-readability-metrics` depends on NLTK tokenizers (`punkt` / `punkt_tab`), which attempt to download external model files from the internet upon initial execution. In offline, air-gapped, or sandboxed test environments, this triggers blocking network timeouts or crashes.
- `textstat` is lightweight, deterministic, completely offline, and computes both Flesch Reading Ease and Flesch-Kincaid Grade scores in <1ms without requiring remote corpus downloads.
- When `py-readability-metrics` is preferred, the port interface isolates the implementation so either engine can satisfy the contract.

### Alternatives Considered
- **NLTK punkt download on startup**: High failure risk in CI/CD runners with restricted outbound internet access.
- **Custom heuristic syllable counter**: Prone to variance and non-standard scoring compared to validated libraries.

---

## 3. Pipeline Orchestration & Multi-Agent Architecture

### Background & Needs
The RFP intake process requires a multi-stage workflow:
1. Validity screening (Classifier)
2. Metadata extraction & department scoping (Orchestrator)
3. Domain-specific evaluation (Warehouse, Last Mile, Reverse Logistics workers)
4. Commercial summary & policy cross-check (Synthesizer)

### Decision
Build a dedicated LangGraph workflow `rfp_intake_graph` within `services/api/application/agent/rfp_intake_pipeline.py`.
- **Node 1: `classifier_node`**: Evaluates converted Markdown. If document is non-RFP (e.g. carrier pitch, spam), sets `is_rfp = False`, logs rejection reason, and routes directly to `discard_ticket_node`.
- **Node 2: `orchestrator_node`**: Extracts client metadata, operational country, currency (`EUR` for `ES`, `USD` for `US`), volume, and requested services. Determines `departments_needed` (`warehouse`, `lastmile`, `reverse`).
- **Node 3: `department_workers_fanout`**: Invokes only the workers present in `departments_needed`. Omitted departments are bypassed.
  - `warehouse_worker` (Ana Whitfield)
  - `lastmile_worker` (Carlos Vega)
  - `reverse_worker` (Sofía Ramos)
- **Node 4: `synthesizer_node`**: Aggregates findings, compares against TrackFlow company policies (`trackflow-returns-policy.es.md`, `trackflow-sla-delivery.es.md`, `trackflow-storage-pricing.es.md`), highlights contradictions, and drafts executive synthesis.
- **Node 5: `finalize_node`**: Persists `DepartmentSection` records, writes `IntakeHandoffPayload`, and transitions status to `analisis_completo`.

### Rationale
- Fits TrackFlow's existing LangGraph runtime (`langgraph>=1.2.22`).
- State is strongly typed with `RFPState(TypedDict)` enforcing contract safety.
- Dynamic conditional routing natively prevents unneeded workers from executing.
- Each node can be unit-tested in isolation using mock LLM responses or deterministic prompt testers.

### Alternatives Considered
- **Linear Celery task chain**: Lacks dynamic graph branch-and-merge capabilities and typed state passing.
- **Single monolithic LLM prompt**: Risks prompt bloat, high token costs, and increased hallucination when combining department perspectives.

---

## 4. Zero-Hallucination & Policy Verification Guardrails

### Background & Needs
Clarification Q2 and Success Criterion SC-004 require 100% zero fabrication of missing numbers (e.g., pallet dimensions, volume tiers, return rates). Clarification Q4 mandates checking claims against TrackFlow policy rules.

### Decision
1. **Zero Hallucination Guardrail**:
   - Worker prompt system instructions explicitly state: *"You MUST NOT assume, estimate, or invent pallet counts, product dimensions, or SLAs not in the document. Any missing information MUST be recorded in `open_questions`."*
   - Pydantic output schemas require an explicit `open_questions: List[str]` field.
2. **Deterministic Policy Rules in Synthesizer**:
   - Rule A (Reverse Turnaround): Returns turnaround promise < 48 hours flagged as contradiction (standard policy requires manual receiving, inspection, and classification).
   - Rule B (Warehouse Capacity): Monthly volume > 20,000 orders/month flagged for capacity review with Ana Whitfield.
   - Rule C (Currency Alignment): Operating country `ES` requesting `USD` or `US` requesting `EUR` flagged as currency mismatch.
   - Rule D (Cross-Border Returns): Requests for international returns without manual authorization flagged per policy.
   - Rule E (Unsupported Services): Services outside warehouse, last mile, and reverse logistics (e.g. air freight, cold storage) cataloged as `unsupported_services`.

### Rationale
Deterministic validation combined with targeted LLM reasoning provides guaranteed compliance with business constraints while preserving natural language flexibility.

---

## 5. Persistence & Asynchronous Execution Architecture

### Background & Needs
Constitution Principle I (Service Boundaries) and Principle II (Non-blocking async execution) require non-blocking HTTP endpoints, dependency injection, and clean SQLModel persistence.

### Decision
1. **Asynchronous Execution Pattern**:
   - `POST /api/v1/rfp/intake`: Receives PDF upload, writes file to `data/raw/{ticket_id}_{filename}`, inserts `IntakeTicket` in PostgreSQL with status `analizando`, queues background execution via FastAPI `BackgroundTasks` (running pipeline in threadpool), and returns HTTP 202 in <100ms.
   - `GET /api/v1/rfp/tickets/{ticket_id}`: Allows client polling or view retrieval with full ticket details.
2. **Database Schema (SQLModel / PostgreSQL)**:
   - Tables: `intake_tickets`, `rfp_metadata`, `department_sections`, `intake_handoff_payloads`.
   - Repositories: `SQLModelIntakeTicketRepository` implementing `IntakeTicketRepositoryPort`.
   - Transaction boundaries: Any top-level exception during background execution executes `ticket.mark_discarded(error_message)` within a transactional rollback block, ensuring no orphan `analizando` states.

---

## 6. Frontend Architecture (`uis/backoffice`)

### Background & Needs
Constitution Principle III (Strict TypeScript), Principle IV (Defensive UI Error States), and Principle V (Performance & Core Web Vitals) govern the backoffice user interface.

### Decision
Create a Next.js App Router module under `uis/backoffice/app/rfp/`:
- `uis/backoffice/app/rfp/page.tsx`: Ingestion dashboard and ticket list.
- `uis/backoffice/app/rfp/[id]/page.tsx`: Ticket detail and review view.
- Components:
  - `RFPUploadForm`: Drag-and-drop PDF uploader with size/type validation.
  - `TicketStatusBadge`: Visual indicator (`analizando`, `analisis_completo`, `descartado`).
  - `ReadabilityMetricCard`: Visual gauge for Reading Ease and Grade Level.
  - `DepartmentKeyAspectsCard`: Accordion/tabs for Warehouse, Last Mile, and Reverse Logistics.
  - `ContradictionsAlert`: Warning banner highlighting policy conflicts and unsupported services.
  - `HandoffJsonViewer`: Expandable JSON preview for Part 2 handoff verification.
- Shared Types: Add `@repo/shared-types/types/rfp.ts` exported via `packages/shared/types/index.ts`.
