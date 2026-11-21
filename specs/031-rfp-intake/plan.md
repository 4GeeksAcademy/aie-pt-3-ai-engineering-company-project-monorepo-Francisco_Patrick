# Implementation Plan: RFP Intake & Agentic Analysis Pipeline (Part 1 of 3)

**Branch**: `031-rfp-intake` | **Date**: 2026-11-21 | **Spec**: [specs/031-rfp-intake/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/031-rfp-intake/spec.md)

**Input**: Feature specification from `specs/031-rfp-intake/spec.md`

---

## Summary

Implement an asynchronous proposal intake and agentic analysis pipeline (Part 1 of 3) for TrackFlow.
The system ingests raw customer proposal PDF files via the backoffice web UI or REST API, immediately returning HTTP 202 with a tracked ticket. In the background, the PDF is stored under `data/raw/`, converted to structured Markdown, analyzed for readability metrics (Flesch Reading Ease and Grade Level), and screened by a Classifier Agent to cleanly discard non-RFP solicitations (such as carrier rate pitches or spam) with logged reasons.

For genuine RFPs, a dedicated LangGraph orchestrator extracts standardized commercial metadata (`client_name`, `client_country`, `currency`, `monthly_volume`, `deadline`) and scopes execution strictly to needed departments (`warehouse`, `lastmile`, `reverse`). Department workers analyze domain requirements with zero fabrication (recording unknowns in `open_questions`). A Synthesizer Agent evaluates findings against TrackFlow company policies, flags contradictions, compiles an executive briefing for Sales (Miguel Torres), updates ticket status to `analisis_completo`, and persists an immutable Part 2 handoff payload in PostgreSQL (Supabase) via SQLModel.

---

## Technical Context

**Language/Version**: Python 3.14 (Backend `services/api`), TypeScript 5.8 / Node.js 20+ (Frontend `uis/backoffice`, `packages/shared`)  
**Primary Dependencies**:
- Backend: `fastapi>=0.141.1`, `sqlmodel>=0.0.42`, `pydantic>=2.13.5`, `langgraph>=1.2.22`, `pypdf>=7.1.1`, `textstat>=0.7.13`, `psycopg2-binary`
- Frontend: `next@15.x` (App Router), `react@19.x`, `@repo/shared-types`, `tailwindcss@3.4.x`, `lucide-react`  
**Storage**: PostgreSQL (Supabase) via SQLModel persistence adapters (`intake_tickets`, `rfp_metadata`, `department_sections`, `intake_handoff_payloads`), file storage under `data/raw/` for raw PDFs  
**Testing**: `pytest` (backend unit and integration tests), Jest / React Testing Library (`uis/backoffice`)  
**Target Platform**: Linux server / Windows development environment, Web browsers (Chrome, Firefox, Safari)  
**Project Type**: Monorepo Web Application (FastAPI backend + Next.js App Router backoffice frontend + shared TypeScript package)  
**Performance Goals**:
- HTTP 202 upload acknowledgment in `< 500ms` (non-blocking)
- Markdown conversion and readability computation in `< 1.5s`
- End-to-end background agent analysis completion in `< 15s`
- UI Core Web Vitals: LCP $\le$ 1.0s, TBT $\le$ 200ms, CLS = 0  
**Constraints**:
- Strictly zero hallucination / fabrication of missing operational data (enforced via explicit `open_questions` schema)
- Strict compliance with `trackflow-BRIEFING.es.md` department universe (`warehouse`, `lastmile`, `reverse`)
- Currency strictly tied to client country (`ES` $\rightarrow$ `EUR`, `US` $\rightarrow$ `USD`)
- Transactional crash safety: no ticket orphaned in `analizando` state  
**Scale/Scope**: ~50-100 RFP proposals/month, documents up to 25MB / 50 pages, 3 active department workers

---

## Constitution Check

*GATE: Evaluated before Phase 0 research. Re-evaluated post-design.*

| Principle | Requirement | Plan Compliance Status | Validation Mechanism |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Frontends reside in `uis/`, backend in `services/api/` with layered architecture; contracts shared via `packages/shared/`. No direct DB access from UI. | **PASSED** | Backoffice consumes only `/api/v1/rfp/*` REST API. Domain models (`domain/rfp/`), adapters (`infrastructure/`), and controllers (`presentation/api/v1/rfp.py`) remain strictly encapsulated. Shared DTOs defined in `@repo/shared-types`. |
| **II. Public API Compatibility & Strict Contract Serialization** | Explicit Pydantic `response_model`, `Depends` injection, non-blocking async execution (run sync I/O in threadpool/background tasks), DTO projections. | **PASSED** | Endpoint `/api/v1/rfp/intake` returns HTTP 202 immediately with `IntakeTicketAcceptedResponse`. Sync PDF conversion and agent runs execute in `BackgroundTasks`. Domain entities never leak; projected via dedicated response schemas. |
| **III. Strict TypeScript & Static Type Safety** | `strict: true`, zero `any`, explicit return types, JSDoc comments, `import type`. | **PASSED** | All frontend and `@repo/shared-types` code will strictly enforce zero `any` and export typed interfaces for tickets, metadata, and handoff payloads. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | No raw stack traces in 500s, sanitized errors, no swallowed exceptions, resilient UI error states. | **PASSED** | Global try-catch boundaries on background pipeline catch failures and persist sanitized error messages on tickets. Frontend handles network errors with retry CTAs. |
| **V. Performance-First Architecture & Core Web Vitals** | LCP $\le$ 1.0s, TBT $\le$ 200ms, CLS = 0. Baseline ES2022. Dynamic code splitting. | **PASSED** | Backoffice RFP dashboard uses Next.js App Router with server-rendered baseline and client polling component. Heavy JSON inspection trees dynamically imported. |
| **VI. Test-First Development & Deterministic Gates** | Unit and integration test coverage for critical logic, passing typecheck and builds. | **PASSED** | Full unit tests for classifier agent, orchestrator scoping, department workers, and synthesizer policy checks, plus API integration tests. |
| **VII. Vector Database & Qdrant SDK Governance** | Encapsulated repository ports if vector knowledge retrieval is invoked. | **PASSED** | Qdrant access (if policy lookup RAG is queried) strictly passes through existing `VectorStorePort` in `infrastructure/adapters/`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/031-rfp-intake/
├── spec.md                 # Feature specification
├── plan.md                 # Implementation plan (this file)
├── research.md             # Phase 0 research & technology decisions
├── data-model.md           # Phase 1 domain entities, schema & state machine
├── contracts/              # Phase 1 contracts
│   ├── rfp-intake-api.yaml          # OpenAPI 3.1 specification for REST endpoints
│   ├── rfp-state-contract.json      # LangGraph state & node output JSON schemas
│   └── handoff-payload-schema.json  # Part 2 handoff JSON schema
└── quickstart.md           # Phase 1 validation & test execution guide
```

### Source Code Layout

```text
services/api/
├── application/
│   └── agent/
│       ├── rfp_intake_pipeline.py       # LangGraph state graph & node wiring
│       ├── rfp_classifier_agent.py      # RFP screening & validity agent
│       ├── rfp_orchestrator_agent.py    # Metadata extraction & department scoper
│       ├── rfp_department_workers.py    # Warehouse, LastMile, Reverse workers
│       └── rfp_synthesizer_agent.py     # Sales synthesis & policy cross-checker
├── domain/
│   └── rfp/
│       ├── entities.py                  # Domain models, value objects, TicketStatus enum
│       ├── exceptions.py                # Custom domain exceptions (NonRFPError, etc.)
│       └── ports.py                     # Repository, DocumentConverter, Readability ports
├── infrastructure/
│   ├── adapters/
│   │   ├── pdf_to_markdown_adapter.py   # PDF text extraction & Markdown formatter
│   │   └── textstat_readability.py      # Readability calculation adapter
│   └── persistence/
│       └── sqlmodel/
│           ├── models.py                # SQLModel table definitions (updated)
│           └── rfp_repository.py        # SQLModel implementation of IntakeTicketRepositoryPort
├── presentation/
│   ├── api/v1/
│   │   └── rfp.py                       # FastAPI router for /api/v1/rfp/*
│   └── schemas/
│       └── rfp.py                       # Pydantic request & response schemas
└── tests/
    ├── unit/
    │   └── agent/
    │       ├── test_rfp_classifier.py
    │       ├── test_rfp_orchestrator.py
    │       ├── test_rfp_department_workers.py
    │       └── test_rfp_synthesizer.py
    └── integration/
        └── test_rfp_intake_api.py

uis/backoffice/
├── app/
│   └── rfp/
│       ├── page.tsx                     # RFP intake dashboard & upload dropzone
│       └── [id]/
│           └── page.tsx                 # RFP ticket analysis detail & synthesis view
└── components/
    └── rfp/
        ├── RFPUploadForm.tsx            # PDF upload drag-and-drop form
        ├── TicketStatusBadge.tsx        # Status chip (analizando/descartado/analisis_completo)
        ├── ReadabilityMetricCard.tsx    # Flesch score gauges & statistics
        ├── DepartmentKeyAspectsCard.tsx # Domain findings & open questions tabs
        └── HandoffJsonViewer.tsx        # Part 2 handoff preview drawer

packages/shared/
└── types/
    ├── index.ts                         # Export barrel (updated)
    └── rfp.ts                           # Shared TypeScript DTOs & status types
```

**Structure Decision**: Multi-project Monorepo (FastAPI backend in `services/api/`, Next.js frontend in `uis/backoffice/`, and TypeScript types in `packages/shared/types/rfp.ts`). Follows existing TrackFlow codebase conventions and constitutional boundary rules.

---

## Complexity Tracking

> **No Constitution violations detected.** All architectural gates adhere strictly to TrackFlow Monorepo Constitution v1.1.0.

| Area | Approach | Rationale / Defense |
|---|---|---|
| PDF Conversion | Decoupled adapter with `pypdf` extraction + Markdown formatting | Eliminates ONNX native DLL dependencies on Windows while providing pure-Python, deterministic extraction. |
| Readability Metrics | `textstat` engine | Eliminates runtime NLTK model downloads, enabling resilient offline and CI/CD operation. |
| Worker Scoping | Conditional LangGraph fan-out | Activates only departments requested by the customer, omitting inactive domains and saving LLM compute. |
| Zero Hallucination | Explicit `open_questions` collection | Eliminates guess-work for missing operational metrics (pallet counts, SLAs). |
