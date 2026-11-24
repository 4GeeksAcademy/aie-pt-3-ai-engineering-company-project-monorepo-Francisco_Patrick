# Implementation Plan: RFP Approval, Arbitration & Document Synthesis (Part 3 of 3)

**Branch**: `033-rfp-approval-completion` | **Date**: 2026-11-22 | **Spec**: [specs/033-rfp-approval-completion/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/033-rfp-approval-completion/spec.md)

**Input**: Feature specification from `specs/033-rfp-approval-completion/spec.md`

---

## Summary

Implement Part 3 of the TrackFlow RFP Agentic Pipeline: Human-in-the-Loop (HITL) Department Approvals, Deterministic Arbitration, and Automatic Final Document Synthesis.
Part 3 accepts the evaluated department drafts from Part 2, transitions the ticket status to `esperando_aprobación` (`waiting_for_approval`), and establishes independent, scoped human-review checkpoints for each active operational department:
- Ana Whitfield (`warehouse`)
- Carlos Vega (`lastmile`)
- Sofía Ramos (`reverse`)

Each department lead can independently review, approve, reject, or request changes on their section without blocking or delaying other departments. State persistence and suspension rely on LangGraph persistent checkpointers namespaced per ticket and department. If cross-department contradictions arise (e.g. warehouse capacity < last mile volume, returns SLA < 48 hours, or currency mismatches), a dedicated deterministic arbitration node enforces briefing business rules under named arbiters (Miguel Torres, Commercial Director; Sofía Ramos, Reverse Logistics Lead) without stochastic LLM debate. Revision loops are capped at a maximum of 2 revisions (3 total attempts). Once all active departments record approval, the pipeline automatically synthesizes the complete proposal into `FinalDocument`, persisting all records and transitioning the ticket to `terminado` (`done`).

---

## Technical Context

**Language/Version**: Python 3.14 (Backend `services/api/`, pipelines `data/pipelines/`), TypeScript 5.8 (`packages/shared/`, `uis/backoffice/`)  
**Primary Dependencies**:
- Backend: `fastapi>=0.141.1`, `sqlmodel>=0.0.42`, `pydantic>=2.13.5`, `langgraph>=1.2.22`, `psycopg2-binary`
- Shared Contracts: `@repo/shared-types` (`packages/shared/types/rfp.ts`)  
**Storage**: PostgreSQL (Supabase) via SQLModel repository abstractions (`intake_tickets`, `rfp_metadata`, `department_sections`, `arbitration_logs`, `final_documents`); LangGraph checkpoints via `SqliteSaver` (local/test) and `PostgresSaver` (staging/production)  
**Testing**: `pytest` (unit and pipeline tests under `tests/pipelines/` and `services/api/tests/`), Jest / RTL (`uis/backoffice/__tests__/`)  
**Target Platform**: Linux server / Windows dev environment, modern web browsers  
**Project Type**: Monorepo Full-Stack Agentic Pipeline & Web Interface  
**Performance Goals**:
- Scoped branch resume and state progression in `< 2s`
- Deterministic conflict evaluation in `< 500ms`
- Automatic final document synthesis in `< 5s`
- End-to-end automated pipeline runtime (excluding human pause time) in `< 60s`  
**Constraints**:
- Strictly non-blocking parallel branch approvals: approving department A must not wait for or block department B
- Zero stochastic LLM voting in arbitration: conflicts resolve deterministically via briefing rules and named arbiters
- Hard iteration cap (max 2 revisions / 3 total attempts) with graceful escalation to Miguel Torres
- Zero data loss: all Part 1 and Part 2 fields, PDF paths, and evaluation scores must persist intact into `FinalDocument`
- Strict TypeScript (`strict: true`, zero `any`, explicit return types)  
**Scale/Scope**: 3 operational departments (`warehouse`, `lastmile`, `reverse`), concurrent multi-department RFP tickets

---

## Constitution Check

*GATE: Evaluated before Phase 0 research. Re-evaluated post-design.*

| Principle | Requirement | Plan Compliance Status | Validation Mechanism |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Frontends in `uis/`, backend in `services/api/` and `data/pipelines/`. No direct DB file access from frontends; shared DTOs in `packages/shared/`. Hexagonal architecture in backend. | **PASSED** | Pipeline orchestration resides in `data/pipelines/rfp_approval_completion/` and `services/api/application/agent/`. Persistence is isolated in SQLModel repositories. Frontends consume only HTTP REST endpoints. |
| **II. Public API Compatibility & Strict Contract Serialization** | Explicit Pydantic `response_model`, `Depends` injection, non-blocking async execution (run sync operations in threadpools / background tasks), DTO projections. | **PASSED** | Approval and resume endpoints in `services/api/presentation/api/v1/rfp.py` declare explicit Pydantic response models (`TicketDetailResponse`, `DepartmentApprovalResponse`), use `Depends`, and project safe DTOs. |
| **III. Strict TypeScript & Static Type Safety** | `strict: true`, zero `any`, explicit return types, JSDoc comments, `import type`. | **PASSED** | `@repo/shared-types` updated with strict interfaces for `ArbitrationLogDTO`, `FinalDocumentDTO`, and `ResumeDecisionDTO`. Backoffice components use explicit typing and JSDoc. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | No raw stack traces in 500s, sanitized errors, no swallowed exceptions, resilient UI error states. | **PASSED** | Resume validation rejects malformed payloads with HTTP 422; duplicate resumes return HTTP 409. UI displays informative banners and retry controls without corrupted states. |
| **V. Performance-First Architecture & Core Web Vitals** | LCP $\le$ 1.0s, TBT $\le$ 200ms, CLS = 0. Dynamic code splitting and deferred evaluation. | **PASSED** | Approval panel components are rendered lazily and use optimistic UI updates where appropriate without blocking initial SSR hydration. |
| **VI. Test-First Development & Deterministic Gates** | Unit and integration test coverage for critical logic, passing typecheck and builds. | **PASSED** | Comprehensive test suite under `tests/pipelines/` verifying scoped interrupts, resume validation, branch independence, iteration limits, and all 3 arbitration triggers. |
| **VII. Vector Database & Qdrant SDK Governance** | Encapsulated repository ports if vector knowledge retrieval is invoked. | **PASSED** | Part 3 processes structured drafts and metadata; any auxiliary knowledge lookups strictly use `VectorStorePort` with offline mock fallbacks. |

---

## Project Structure

### Documentation (this feature)

```text
specs/033-rfp-approval-completion/
├── spec.md                 # Feature specification
├── plan.md                 # Implementation plan (this file)
├── research.md             # Phase 0 research & technology decisions
├── data-model.md           # Phase 1 domain entities, schema & state machine
├── contracts/              # Phase 1 contracts
│   ├── rfp-approval-api.yaml           # OpenAPI 3.1 specification for approval & synthesis endpoints
│   ├── resume-decision.schema.json     # JSON Schema for human approval/rejection resume payload
│   ├── arbitration-log.schema.json     # JSON Schema for deterministic conflict arbitration records
│   └── final-document.schema.json      # JSON Schema for synthesized commercial proposal document
└── quickstart.md           # Phase 1 validation & test execution guide
```

### Source Code Layout

```text
data/pipelines/
└── rfp_approval_completion/
    ├── __init__.py                      # Package exports
    ├── pipeline.py                      # Part 3 LangGraph pipeline & checkpointer orchestration
    ├── arbitration.py                   # Deterministic arbitration node & briefing rules engine
    ├── synthesis.py                     # Final proposal document consolidation & currency binding
    └── state.py                         # LangGraph Part 3 state TypedDict & execution tracer

services/api/
├── application/
│   └── agent/
│       ├── rfp_approval_service.py      # Application service managing approval, resume & synthesis
│       └── rfp_arbitration_agent.py     # Application agent wrapper for conflict evaluation
├── domain/
│   └── rfp/
│       ├── entities.py                  # Extended domain entities: ArbitrationLog, FinalDocument, ApprovalStatus
│       └── ports.py                     # Extended IntakeTicketRepositoryPort for arbitration & final documents
├── infrastructure/
│   └── persistence/
│       └── sqlmodel/
│           ├── models.py                # SQLModel tables: ArbitrationLogTable, FinalDocumentTable
│           └── rfp_repository.py        # Updated repository methods for approval & final document persistence
└── presentation/
    ├── api/v1/
    │   └── rfp.py                       # REST endpoints: /tickets/{id}/resume-approval, /tickets/{id}/final-document
    └── schemas/
        └── rfp.py                       # Pydantic schemas: ResumeDecisionRequest, ArbitrationLogResponse, FinalDocumentResponse

packages/shared/
└── types/
    └── rfp.ts                           # Shared TypeScript interfaces for Part 3 approvals, arbitration, and final documents

uis/backoffice/
├── app/
│   └── rfp/
│       └── [id]/
│           └── page.tsx                 # Extended RFP ticket detail page hosting DepartmentApprovalPanel
└── components/
    └── rfp/
        ├── DepartmentApprovalPanel.tsx  # Department approval review cards with actions
        ├── ArbitrationLogViewer.tsx     # Conflict log audit timeline
        └── FinalDocumentViewer.tsx      # Consolidated final proposal viewer and export

tests/
└── pipelines/
    ├── test_rfp_approval_interrupts.py  # Unit tests: scoped interrupts & branch independence
    ├── test_rfp_arbitration.py          # Unit tests: volume-vs-capacity, returns-sla-breach, currency-mismatch
    ├── test_rfp_final_synthesis.py      # Unit tests: automatic document compilation & ticket done state
    └── test_rfp_e2e_complete.py         # End-to-end test driving Parts 1 -> 2 -> 3
```

**Structure Decision**: Monorepo layout strictly preserving Constitution Principles I, II, and VI. Pipeline logic resides in `data/pipelines/rfp_approval_completion/`, integrated with `services/api/` via application services, and rendered in `uis/backoffice/` using shared types from `packages/shared/types/rfp.ts`.

---

## Complexity Tracking

> **No Constitution violations detected.** All architectural gates adhere strictly to TrackFlow Monorepo Constitution v1.1.0.

| Area | Approach | Rationale / Defense |
|---|---|---|
| Scoped Interruption | Independent branch interrupts via LangGraph checkpointer | Allows each operational department lead to review and approve without blocking peer leads, fulfilling SC-001. |
| Deterministic Arbitration | Dedicated rule-based arbitration node without LLM debate | Guarantees 100% policy enforcement according to briefing §7 under named arbiters Miguel Torres and Sofía Ramos. |
| Iteration Caps | Enforced limit of 2 revisions (max 3 attempts) | Bounded loops prevent infinite revisions and API bill inflation, escalating unresolved issues to Commercial Director. |
| Final Synthesis Trigger | Conditional graph edge checking all active department approvals | Guarantees incomplete or unapproved proposals are never released or marked finished. |
