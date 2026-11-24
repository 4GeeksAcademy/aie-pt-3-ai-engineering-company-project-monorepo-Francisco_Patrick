# Implementation Plan: RFP Response Generation & Department Drafting Pipeline (Part 2 of 3)

**Branch**: `feature/rfp-response-generation` | **Date**: 2026-11-22 | **Spec**: [specs/032-rfp-response-generation/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/032-rfp-response-generation/spec.md)

**Input**: Feature specification from `specs/032-rfp-response-generation/spec.md`

---

## Summary

Implement the RFP Response Generation & Department Drafting Pipeline (Part 2 of 3) for TrackFlow.
Part 2 directly consumes the validated Part 1 handoff payload (`ticket_id`, RFP metadata, per-department `key_aspects`, and sales synthesis) from PostgreSQL without re-parsing raw PDFs. It transitions the ticket status from `analisis_completo` to `generando_borrador` (`drafting`) and triggers dedicated department proposal generator agents for each active department (`warehouse`, `lastmile`, `reverse`).

Each generated section draft undergoes parallel evaluation across three dimensions: Readability (`textstat` / `py-readability-metrics`), Relevance (coverage of Part 1 `key_aspects` and open questions), and Compliance (strict enforcement of the 5 business rules in `trackflow-BRIEFING.es.md` §5). Sections that fail evaluation enter an automated generator–evaluator revision loop with a default iteration cap of 2 revisions (max 3 total attempts per section). If a section fails after 3 attempts, it gracefully escalates to `needs_human_review` without discarding the ticket. When all active sections complete (passed or capped), state persists in PostgreSQL (Supabase) via SQLModel and an immutable Part 3 handoff payload is compiled.

---

## Technical Context

**Language/Version**: Python 3.14 (Backend `services/api`, `data/pipelines/`), TypeScript 5.8 (`packages/shared`, `uis/backoffice`)  
**Primary Dependencies**:
- Backend: `fastapi>=0.141.1`, `sqlmodel>=0.0.42`, `pydantic>=2.13.5`, `langgraph>=1.2.22`, `textstat>=0.7.13`, `psycopg2-binary`
- Shared Types: `@repo/shared-types` (`packages/shared/types/rfp.ts`)  
**Storage**: PostgreSQL (Supabase) via SQLModel repository abstractions (`intake_tickets`, `rfp_metadata`, `department_sections`, `part3_handoff_payloads`)  
**Testing**: `pytest` (unit tests in `services/api/tests/unit/agent/`, integration tests in `services/api/tests/integration/`, pipeline tests in `tests/pipelines/`)  
**Target Platform**: Linux server / Windows development environment, Web browsers  
**Project Type**: Monorepo Backend Service & Agentic Pipeline (`services/api/` + `data/pipelines/`)  
**Performance Goals**:
- Department draft generation in `< 60s` per iteration
- Multi-dimensional parallel evaluation in `< 5s`
- Zero database write contention or lock timeouts during concurrent department evaluations  
**Constraints**:
- Strict enforcement of the 5 briefing compliance rules (§5): currency mapping, on-time SLA, returns turnaround $\ge 48$ hours, volume discount table, and concealed carrier rates
- Strict iteration cap ($\le 3$ total attempts per department section)
- Graceful escalation: no ticket discarding (`descartado`) on cap exhaustion; status transitions to `needs_human_review`
- Encapsulated vector retrieval: any semantic knowledge queries must pass through `VectorStorePort` with graceful fallbacks  
**Scale/Scope**: 3 operational departments (`warehouse`, `lastmile`, `reverse`), up to 3 generation attempts per active section

---

## Constitution Check

*GATE: Evaluated before Phase 0 research. Re-evaluated post-design.*

| Principle | Requirement | Plan Compliance Status | Validation Mechanism |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Frontends in `uis/`, backend in `services/api/` and `data/pipelines/` with layered architecture; contracts shared via `packages/shared/`. No direct DB access from outside persistence adapters. | **PASSED** | Pipeline runs under `data/pipelines/rfp_response_generation/` and is exposed via `services/api/application/agent/` and FastAPI routes in `services/api/presentation/api/v1/rfp.py`. Persistence uses SQLModel repository adapters. |
| **II. Public API Compatibility & Strict Contract Serialization** | Explicit Pydantic `response_model`, `Depends` injection, non-blocking async execution (run sync I/O in threadpool/background tasks), DTO projections. | **PASSED** | Route `/api/v1/rfp/{ticket_id}/generate-proposal` returns HTTP 202 immediately. Long-running pipeline executes in `BackgroundTasks`. Endpoints project through explicit Pydantic response models. |
| **III. Strict TypeScript & Static Type Safety** | `strict: true`, zero `any`, explicit return types, JSDoc comments, `import type`. | **PASSED** | Shared contracts in `@repo/shared-types` export typed interfaces for `EvaluationResult`, `DepartmentSectionDraft`, and `Part3HandoffPayload` with zero `any`. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | No raw stack traces in 500s, sanitized errors, no swallowed exceptions, resilient UI error states. | **PASSED** | Top-level try-catch boundaries catch pipeline errors, log tracebacks internally, and persist sanitized error messages on the ticket, transitioning to `needs_human_review` rather than crashing. |
| **V. Performance-First Architecture & Core Web Vitals** | LCP $\le$ 1.0s, TBT $\le$ 200ms, CLS = 0. Baseline ES2022. Dynamic code splitting. | **PASSED** | Generation endpoints operate asynchronously; backoffice UI polls or listens for status updates without blocking render trees. |
| **VI. Test-First Development & Deterministic Gates** | Unit and integration test coverage for critical logic, passing typecheck and builds. | **PASSED** | Comprehensive test suite under `tests/pipelines/test_rfp_response_generation.py` and `services/api/tests/unit/agent/` covering generators, evaluators, compliance failures, and iteration limits. |
| **VII. Vector Database & Qdrant SDK Governance** | Encapsulated repository ports if vector knowledge retrieval is invoked. | **PASSED** | Any knowledge base retrieval uses `VectorStorePort` in `services/api/infrastructure/adapters/` with graceful fallback when Qdrant is unreachable. |

---

## Project Structure

### Documentation (this feature)

```text
specs/032-rfp-response-generation/
├── spec.md                 # Feature specification
├── plan.md                 # Implementation plan (this file)
├── research.md             # Phase 0 research & technology decisions
├── data-model.md           # Phase 1 domain entities, schema & state machine
├── contracts/              # Phase 1 contracts
│   ├── rfp-generation-api.yaml          # OpenAPI 3.1 specification for generation endpoints
│   ├── evaluation-result.schema.json    # JSON Schema for structured EvaluationResult
│   └── part3-handoff.schema.json        # JSON Schema for Part 3 handoff payload
└── quickstart.md           # Phase 1 validation & test execution guide
```

### Source Code Layout

```text
data/pipelines/
└── rfp_response_generation/
    ├── __init__.py                      # Package export
    ├── pipeline.py                      # Dedicated response generation pipeline orchestrator
    ├── evaluator.py                     # Parallel multi-dimensional evaluator engine
    └── compliance_rules.py              # Deterministic §5 compliance rules engine

services/api/
├── application/
│   └── agent/
│       ├── rfp_generator_agents.py      # Department generator agents (Warehouse, LastMile, Reverse)
│       ├── rfp_evaluator_agent.py       # Wrapper agent coordinating readability, relevance, compliance
│       └── rfp_response_service.py      # Application service managing generation lifecycle
├── domain/
│   └── rfp/
│       ├── entities.py                  # Extended TicketStatus, EvaluationResult, Part3HandoffPayload
│       └── ports.py                     # Extended IntakeTicketRepositoryPort for drafting & handoff
├── infrastructure/
│   └── persistence/
│       └── sqlmodel/
│           ├── models.py                # Updated DepartmentSectionTable & new Part3HandoffPayloadTable
│           └── rfp_repository.py        # Updated repository methods for draft & handoff persistence
└── presentation/
    ├── api/v1/
    │   └── rfp.py                       # Extended endpoints for generate-proposal, sections, part3-handoff
    └── schemas/
        └── rfp.py                       # Updated Pydantic request/response schemas

packages/shared/
└── types/
    └── rfp.ts                           # Updated TypeScript interfaces for Part 2 & Part 3 handoff

tests/
└── pipelines/
    └── test_rfp_response_generation.py  # Pipeline unit & integration tests
```

**Structure Decision**: Monorepo layout adhering to Constitution Principles I and II. The generation pipeline resides in `data/pipelines/rfp_response_generation/` (in compliance with FR-016 and briefing §2.4) and is consumed by `services/api/` application services and FastAPI presentation routes.

---

## Complexity Tracking

> **No Constitution violations detected.** All architectural gates adhere strictly to TrackFlow Monorepo Constitution v1.1.0.

| Area | Approach | Rationale / Defense |
|---|---|---|
| Parallel Evaluation | Concurrent modular execution (Readability + Relevance + Deterministic Compliance) | Ensures 100% deterministic detection of critical briefing policy infractions without relying on stochastic LLM behavior. |
| Department Independence | Isolated generator–evaluator loop per department | Prevents passing departments from repeating expensive LLM generation when an unrelated department requires revision. |
| Escalation Mechanism | Non-destructive `needs_human_review` fallback | Bounded to 3 attempts, preventing runaway LLM billing and avoiding discarding customer proposal opportunities. |
| Knowledge Lookup | Encapsulated `VectorStorePort` with default briefing fallback | Upholds Constitution Principle VII and ensures unit tests run offline without live Qdrant infrastructure. |
