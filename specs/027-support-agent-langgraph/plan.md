# Implementation Plan: Support Agent with LangGraph — Explicit Reasoning & Operational Tools Outside the RAG

**Branch**: `027-support-agent-langgraph` | **Date**: 2026-11-18 | **Spec**: [specs/027-support-agent-langgraph/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/027-support-agent-langgraph/spec.md)

**Input**: Feature specification from `/specs/027-support-agent-langgraph/spec.md`

---

## Summary

The objective of this feature is to evolve TrackFlow's Support Agent from a single-source static policy RAG state machine into a multi-source autonomous reasoning workflow powered by a compiled LangGraph `StateGraph`. Building upon the Part 1 foundation (`intake`, `retrieval`, `generation`, `refusal`), Part 2 equips the agent with two distinct, single-responsibility, strictly read-only operational tools:
1. **Support Ticket Query Tool (`ticket_tool`)**: Reads live incident records (`id`, `title`, `description`, `status`, `category`, `origin`, `branch`, `created_at`, `updated_at`) directly from the existing TrackFlow Incident Manager (`IncidentService` / `GET /api/incidents`), capped at 20 most-recent records plus `total_matched`.
2. **Inventory Stock Query Tool (`inventory_tool`)**: Reads live product stock projections (`id`, `sku`, `name`, `description`, `stock`, `min_threshold`, `is_low_stock`) directly from the existing TrackFlow Inventory Manager (`InventoryService` / `GET /inventory/products/{id}`), capped at 20 most-relevant records plus `total_matched`.

At the `intake` stage, the agent autonomously determines from the user's natural-language inquiry whether to invoke `ticket_tool`, `inventory_tool`, static knowledge retrieval (`rag`), or a hybrid combination—executing multi-source plans in the canonical sequence `ticket_tool` → `inventory_tool` → `rag`. Every operational tool call enforces an explicit numerical timeout (defaulting to `4.0` seconds) and transitions to a controlled `tool_fallback` node upon timeout, transport/service error, or missing record (`not_found`), guaranteeing honest inability-to-confirm responses with zero hallucinated statuses or stock quantities (and graceful partial answers when `rag` succeeds in a hybrid query). Every run emits a queryable `AgentTrace` detailing visited nodes, consulted data sources (`sources_consulted`), step latencies, tool outcome statuses, and `MemorySaver` state checkpoints.

---

## Technical Context

**Language/Version**: Python >= 3.14 (executed via `uv` in `services/api`)

**Primary Dependencies**:
- `langgraph` (>= 1.2.22) & `langgraph-checkpoint` (>= 4.3.2)
- `fastapi` (>= 0.141.1) & `pydantic` (>= 2.13.5)
- `qdrant-client` (>= 1.13.0) & `fastembed` (>= 0.5.0)
- `tinydb` (Incident Manager persistence) & `sqlmodel` / `sqlalchemy` (Inventory Manager persistence)
- `pytest` (>= 9.1.1) & `httpx` (>= 0.28.1)

**Storage**:
- Qdrant Vector Database (collection: `trackflow_knowledge`) for static policy RAG
- TinyDB (`db.json` table `incidents`) via `IncidentService` / `TinyDBIncidentRepository` for live support tickets
- SQLite / SQLModel (`inventory.db` tables `sku`, `stock_entry`, `stock_exit`) via `InventoryService` / `SQLModelInventoryRepository` for live product stock
- In-memory thread checkpointer (`MemorySaver`) for LangGraph state persistence
- In-memory thread-safe `TraceRegistry` for queryable post-hoc audit traces

**Testing**:
- Monorepo pipeline evaluations: `tests/pipelines/test_support_agent_evaluation.py`
- Service unit tests: `services/api/tests/unit/test_agent_workflow.py`, `services/api/tests/unit/test_operational_tools.py`
- Service integration tests: `services/api/tests/integration/test_agent_routes.py`

**Target Platform**: Containerized Linux / Windows backend service (FastAPI / Uvicorn)

**Project Type**: Web service / backend microservice with compiled state machine, operational tool adapters, and REST API

**Performance Goals**:
- Explicit `4.0` second numerical timeout (configurable within `3.0`–`5.0` seconds via `AGENT_TOOL_TIMEOUT_SECONDS`) enforced on 100% of operational tool invocations
- P95 latency < 500ms for intake, autonomous intent classification, in-process tool lookups, and vector search
- P99 latency < 50ms for empty query early termination and write-mutation prompt refusal
- 0% blocking synchronous execution on the FastAPI main event loop (offloaded to threadpool via `run_in_threadpool`)

**Constraints**:
- Strict read-only operational tools: zero capability to create, update, transition, or delete tickets, products, or orders (FR-019)
- Strict single-responsibility boundary: `ticket_tool` and `inventory_tool` implemented as separate tools, ports, adapters, and graph nodes (FR-020)
- Real data only: tools read directly from TrackFlow's real Incident Manager and Inventory Manager stores (`db.json` and `inventory.db`) with zero hardcoded or parallel fake datasets in application code (FR-017, FR-018)
- Multi-record filter cap: maximum 20 records returned per tool call (ordered most recent/relevant first) plus `total_matched` count (FR-016, FR-018)
- Canonical hybrid execution sequence: `ticket_tool` → `inventory_tool` → `rag` → `tool_fallback` (if any tool degraded/not_found) → `generation` / `refusal` (FR-023, FR-025)
- Zero raw stack traces or internal server paths exposed across HTTP boundaries (Constitution Principle IV)
- 100% Pydantic DTO projections on API routes with dependency injection via `Depends` (Constitution Principle II)
- Encapsulated vector operations behind `VectorStorePort` (Constitution Principle VII)

**Scale/Scope**:
- 7 single-responsibility workflow nodes (`intake`, `ticket_tool`, `inventory_tool`, `retrieval`, `tool_fallback`, `generation`, `refusal`)
- 5 deterministic conditional routing edges (`route_after_intake`, `route_after_ticket_tool`, `route_after_inventory_tool`, `route_after_retrieval`, `route_after_tool_fallback`)
- 2 typed read-only operational tool ports & adapters (`SupportTicketToolPort` / `IncidentSupportTicketToolAdapter`, `InventoryStockToolPort` / `InventoryStockQueryToolAdapter`)
- 1 compiled graph factory with build-time reachability & dead-end validation
- 1 FastAPI router (`POST /api/v1/agent/query` + `/agent/query`, `GET /api/v1/agent/trace/{id}`, `GET /api/v1/agent/health`)
- 1 automated pipeline evaluation suite (`tests/pipelines/test_support_agent_evaluation.py`) covering Part 1 policy grounding and Part 2 autonomous tool routing, hybrid queries, and honest fallback recovery

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Compliance Status | Analysis & Evidence |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Monorepo architectural boundaries MUST be strictly preserved across all subprojects. Clean hexagonal boundaries in `services/api/`. | **PASS** | Domain entities and tool contracts reside in `domain/agent/`, tool adapters reside in `infrastructure/adapters/`, orchestration workflow lives in `application/services/`, and presentation controllers live in `presentation/api/v1/`. Operational tools access data exclusively through `IncidentService` / `InventoryService` ports or optional HTTP transport. |
| **II. Public API Compatibility & Contract Serialization** | 100% FastAPI endpoints declare explicit `response_model`, `Depends` injection, async non-blocking execution, DTO projections. | **PASS** | Route handlers in `presentation/api/v1/agent.py` inject `SupportAgentService` via `Depends`, wrap execution in `run_in_threadpool`, return `AgentQueryResponseSchema` (backward-compatible with additive trace/tool metadata fields), and shield internal domain primitives. |
| **III. Strict TypeScript & Static Type Safety** | Strict type hygiene; Python type annotations and Pydantic models across domain boundaries. | **PASS** | All Python modules use full type annotations, `TypedDict` for `AgentState`, frozen `@dataclass` for domain entities (`TicketToolInput`, `TicketToolOutput`, `InventoryToolInput`, `InventoryToolOutput`, `AgentTrace`), and Pydantic v2 schemas for presentation DTOs. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw stack traces (`str(e)`) exposed in HTTP 500; sanitized user-safe error messages; credentials loaded from environment. | **PASS** | Tool nodes catch `TimeoutError` and service exceptions within the 4.0s deadline, sanitizing error strings into `TicketToolOutput` / `InventoryToolOutput` and routing to `tool_fallback`. Optional HTTP auth tokens load exclusively from `AGENT_INTERNAL_API_TOKEN` in environment config. |
| **V. Performance-First Architecture** | Responsive execution; offloaded blocking I/O; explicit timeout boundaries; eliminate unnecessary computations. | **PASS** | Every operational tool call is bounded by a strict `4.0`s timeout (`concurrent.futures` / `httpx` timeout). Empty queries and write-mutation prompts terminate early without invoking retrieval or LLM generation. |
| **VI. Test-First Development & Deterministic Verification** | Automated evaluation suite in `tests/pipelines/` runnable via single command; verified policy grounding, tool routing, and fallback honesty; pre-existing tests pass. | **PASS** | `tests/pipelines/test_support_agent_evaluation.py` runs in a single `pytest` command, verifying Part 1 policy grounding (Eval 1–4) plus Part 2 autonomous tool routing (ticket tool vs RAG, inventory tool vs RAG, hybrid inquiry, and unavailable/missing-record tool fallback). |
| **VII. Vector Database & Qdrant SDK Governance** | Vector interactions encapsulated behind `VectorStorePort`; canonical collections; calibrated similarity threshold (0.62); citations included. | **PASS** | Static knowledge retrieval node continues to delegate to `VectorStorePort` (`QdrantVectorStoreAdapter`) with the calibrated `0.62` cosine similarity threshold and document section citations. |

**Gate Outcome (Pre-Phase 0 & Post-Phase 1)**: **PASSED** (7 of 7 principles fully satisfied; zero violations; no complexity tracking exceptions required).

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
│   ├── agent-api.yaml   # OpenAPI 3.1 specification for agent & trace endpoints
│   ├── agent-state.json # JSON Schema for minimal AgentState TypedDict
│   └── tools-schema.json # JSON Schema for TicketTool & InventoryTool input/output contracts
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code Layout

```text
services/api/
├── application/
│   └── services/
│       ├── agent_workflow.py            # LangGraph StateGraph nodes (intake, ticket_tool, inventory_tool, retrieval, tool_fallback, generation, refusal), routing, compilation
│       ├── trace_registry.py            # In-memory thread-safe registry for querying AgentTrace records
│       └── support_agent_service.py     # Application service coordinating compiled graph execution, tool wiring & tracing
├── domain/
│   └── agent/
│       ├── entities.py                  # AgentState TypedDict, TicketToolInput/Output, InventoryToolInput/Output, AgentTrace, AgentCheckpoint
│       ├── exceptions.py                # GraphCompilationError, WorkflowExecutionError, ToolExecutionTimeoutError domain exceptions
│       └── ports.py                     # SupportAgentServicePort, TraceRegistryPort, SupportTicketToolPort, InventoryStockToolPort
├── infrastructure/
│   └── adapters/
│       ├── support_ticket_tool_adapter.py # Read-only SupportTicketToolPort adapter wrapping IncidentService (or optional HTTP client) with 4.0s timeout
│       └── inventory_stock_tool_adapter.py # Read-only InventoryStockToolPort adapter wrapping InventoryService (or optional HTTP client) with 4.0s timeout
├── presentation/
│   ├── api/v1/
│   │   └── agent.py                     # FastAPI routes: POST /query, GET /trace/{trace_id}, GET /health
│   ├── schemas/
│   │   └── agent.py                     # Pydantic request/response DTOs including sources_consulted and tool outcome summaries
│   └── dependencies.py                  # FastAPI dependency injection providers (get_support_ticket_tool_dep, get_inventory_stock_tool_dep, get_support_agent_service)
└── tests/
    ├── unit/
    │   ├── test_agent_workflow.py       # Unit tests for 7-node topology, autonomous routing, canonical ordering, and compilation checks
    │   └── test_operational_tools.py    # Unit tests for TicketTool and InventoryTool read-only contracts, 20-record cap, 4.0s timeout, and not_found/error fallback
    └── integration/
        └── test_agent_routes.py         # Integration tests for FastAPI agent endpoints, live tool queries, fallback responses, and error shielding

tests/
└── pipelines/
    └── test_support_agent_evaluation.py # Monorepo evaluation suite: Part 1 RAG grounding + Part 2 autonomous tool vs RAG routing & honest fallback
```

**Structure Decision**: Hexagonal / Clean Architecture adhering to the existing `services/api/` layout. Domain contracts and tool ports reside in `domain/agent/`, read-only operational tool adapters reside in `infrastructure/adapters/`, the compiled LangGraph workflow and autonomous routing logic reside in `application/services/`, presentation controllers reside in `presentation/api/v1/`, and end-to-end evaluation tests reside in `tests/pipelines/`.

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | N/A | All requirements satisfy monorepo architectural standards and constitution principles without deviation. |
