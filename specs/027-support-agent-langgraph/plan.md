# Implementation Plan: Support Agent with LangGraph

**Branch**: `027-support-agent-langgraph` | **Date**: 2026-11-17 | **Spec**: [specs/027-support-agent-langgraph/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/027-support-agent-langgraph/spec.md)

**Input**: Feature specification from `/specs/027-support-agent-langgraph/spec.md`

---

## Summary

The objective of this feature is to transform the existing black-box RAG question-answering pipeline into an explicit, transparent, and auditable state graph using LangGraph. The implementation refactors reasoning into single-responsibility nodes (`intake`, `retrieval`, `generation`, `refusal`) interconnected by deterministic conditional routing edges. Inquiries below the calibrated cosine similarity threshold (0.62) or containing blank inputs are intercepted before language generation and routed to an honest refusal protocol. Structural integrity is verified at build/compilation time prior to handling runtime traffic. Every execution produces a queryable structured trace (`AgentTrace`) with node sequence and step latencies, while intermediate state is snapshotted via checkpointing (`MemorySaver`). The compiled agent is served via a defensive FastAPI REST endpoint adhering strictly to monorepo hexagonal architecture and serialization standards.

---

## Technical Context

**Language/Version**: Python >= 3.14 (executed via `uv` in `services/api`)

**Primary Dependencies**:
- `langgraph` (>= 1.2.22) & `langgraph-checkpoint` (>= 4.3.2)
- `fastapi` (>= 0.141.1) & `pydantic` (>= 2.13.5)
- `qdrant-client` (>= 1.13.0) & `fastembed` (>= 0.5.0)
- `pytest` (>= 9.1.1) & `httpx` (>= 0.28.1)

**Storage**:
- Qdrant Vector Database (collection: `trackflow_knowledge`)
- In-memory thread checkpointer (`MemorySaver`) for LangGraph state persistence
- In-memory thread-safe `TraceRegistry` for queryable post-hoc audit traces

**Testing**:
- Monorepo pipeline evaluations: `tests/pipelines/test_support_agent_evaluation.py`
- Service unit tests: `services/api/tests/unit/test_agent_workflow.py`
- Service integration tests: `services/api/tests/integration/test_agent_routes.py`

**Target Platform**: Containerized Linux / Windows backend service (FastAPI / Uvicorn)

**Project Type**: Web service / backend microservice with compiled state machine and REST API

**Performance Goals**:
- P95 latency < 500ms for intake, vector search, and conditional routing (excluding external LLM generation)
- P99 latency < 50ms for empty query early termination and below-threshold refusal routing
- 0% blocking synchronous execution on the FastAPI main event loop (offloaded to threadpool via `run_in_threadpool`)

**Constraints**:
- Strict reuse of existing embedding and retrieval adapters (`FastEmbedAdapter`, `QdrantVectorStoreAdapter`) without duplicating vector search logic
- Minimal state schema (`AgentState` TypedDict) passing only query, context chunks, answers, citations, and execution metadata (no full conversational chat history)
- Explicit graph compilation prior to request execution with build-time failure on disconnected or misconfigured nodes
- Zero raw stack traces or internal server paths exposed across HTTP boundaries (Constitution Principle IV)
- 100% Pydantic DTO projections on API routes with dependency injection via `Depends` (Constitution Principle II)
- Encapsulated vector operations behind `VectorStorePort` (Constitution Principle VII)

**Scale/Scope**:
- 4 single-responsibility nodes (`intake`, `retrieval`, `generation`, `refusal`)
- 2 conditional routing edges (`route_after_intake`, `route_after_retrieval`)
- 1 compiled graph factory with build-time validation
- 1 FastAPI router (`POST /api/v1/agent/query`, `GET /api/v1/agent/trace/{id}`, `GET /api/v1/agent/health`)
- 1 automated pipeline evaluation suite with at least 4 verification scenarios

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Compliance Status | Analysis & Evidence |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Monorepo architectural boundaries MUST be strictly preserved across all subprojects. Clean hexagonal boundaries in `services/api/`. | **PASS** | Domain entities live in `domain/agent/`, orchestration workflow lives in `application/services/`, presentation controllers live in `presentation/api/v1/`. No frontend or utility code violates backend boundaries. |
| **II. Public API Compatibility & Contract Serialization** | 100% FastAPI endpoints declare explicit `response_model`, `Depends` injection, async non-blocking execution, DTO projections. | **PASS** | Route handlers in `presentation/api/v1/agent.py` inject `SupportAgentService` via `Depends`, wrap synchronous operations in `run_in_threadpool`, return `AgentQueryResponseSchema`, and prevent internal graph state leakage. |
| **III. Strict TypeScript & Static Type Safety** | Strict type hygiene; Python type annotations and Pydantic models across domain boundaries. | **PASS** | All new Python modules use full type annotations, `TypedDict` for workflow state, dataclasses for domain entities, and Pydantic v2 schemas for presentation DTOs. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw stack traces (`str(e)`) exposed in HTTP 500; sanitized user-safe error messages; PII masked. | **PASS** | Exception shielding middleware and route-level error boundaries intercept unhandled workflow exceptions, log tracebacks internally, and return sanitized `SanitizedErrorResponse` bodies. |
| **V. Performance-First Architecture** | Responsive execution; offloaded blocking I/O; eliminate unnecessary computations. | **PASS** | Empty queries and out-of-scope inquiries conditionally bypass LLM generation, saving compute and latency. All graph runs execute off the main event loop. |
| **VI. Test-First Development & Deterministic Verification** | Automated evaluation suite in `tests/pipelines/` runnable via single command; verified policy grounding; pre-existing test suites pass. | **PASS** | Comprehensive evaluation suite in `tests/pipelines/test_support_agent_evaluation.py` asserts node sequence, refusal routing, and factual policy adherence against `docs/company-knowledge-base/` without breaking existing tests. |
| **VII. Vector Database & Qdrant SDK Governance** | Vector interactions encapsulated behind `VectorStorePort`; canonical collections; calibrated similarity threshold (0.62); citations included. | **PASS** | Retrieval node delegates directly to `VectorStorePort` / `QdrantVectorStoreAdapter`. Strict 0.62 threshold triggers honest refusal. Answers cite source documents and sections. |

**Gate Outcome**: **PASSED** (7 of 7 principles fully satisfied; zero violations; no complexity tracking exceptions required).

---

## Project Structure

### Documentation (this feature)

```text
specs/027-support-agent-langgraph/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── agent-api.yaml   # OpenAPI 3.1 specification for agent endpoints
│   └── agent-state.json # JSON Schema for minimal AgentState TypedDict
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code Layout

```text
services/api/
├── application/
│   └── services/
│       ├── agent_workflow.py            # LangGraph StateGraph nodes, conditional routing, compilation factory
│       ├── trace_registry.py            # In-memory thread-safe registry for querying AgentTrace records
│       └── support_agent_service.py     # Application service coordinating compiled graph execution & tracing
├── domain/
│   └── agent/
│       ├── entities.py                  # AgentState TypedDict, AgentTrace, AgentCheckpoint domain models
│       ├── exceptions.py                # GraphCompilationError, WorkflowExecutionError domain exceptions
│       └── ports.py                     # SupportAgentServicePort, TraceRegistryPort interfaces
├── presentation/
│   ├── api/v1/
│   │   └── agent.py                     # FastAPI routes: POST /query, GET /trace/{trace_id}, GET /health
│   ├── schemas/
│   │   └── agent.py                     # Pydantic request/response DTOs for agent endpoints
│   └── dependencies.py                  # FastAPI dependency injection providers (get_support_agent_service)
└── tests/
    ├── unit/
    │   └── test_agent_workflow.py       # Unit tests for nodes, conditional branching, and compilation checks
    └── integration/
        └── test_agent_routes.py         # Integration tests for FastAPI agent endpoints and error shielding

tests/
└── pipelines/
    └── test_support_agent_evaluation.py # Monorepo evaluation suite: topology, refusal, and factual grounding
```

**Structure Decision**: Hexagonal / Clean Architecture adhering to existing `services/api/` layout. Core agent workflow definitions reside in `application/services/`, domain contracts in `domain/agent/`, presentation controllers in `presentation/api/v1/`, and end-to-end evaluation tests in `tests/pipelines/`.

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | N/A | All requirements satisfy monorepo architectural standards and constitution principles without deviation. |
