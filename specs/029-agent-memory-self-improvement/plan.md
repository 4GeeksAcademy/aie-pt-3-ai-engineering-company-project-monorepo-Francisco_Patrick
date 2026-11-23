# Implementation Plan: Agent Memory & Self-Improvement (Part 1 of 2)

**Branch**: `029-agent-memory-self-improvement` | **Date**: 2026-11-21 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/029-agent-memory-self-improvement/spec.md)

**Input**: Feature specification from `specs/029-agent-memory-self-improvement/spec.md`

## Summary

Extend TrackFlow's existing LangGraph Support Agent with persistent cross-session operational memory (carrier coverage constraints, recurring incident context, and B2B client reporting preferences). The solution maintains strict storage isolation from company static knowledge (Qdrant `*_knowledge` collections remain 100% read-only), performs candidate self-evaluation within a single conversational turn (< 100ms overhead, zero secondary evaluator LLMs), applies explicit user confirmation with structured intent classification (`approve`, `reject`, `edit`, `unrelated_or_ambiguous`), defaults safely to discarding proposals on ambiguity or topic shifts, logs every proposal transition in an immutable audit log, bounds storage growth via carrier-country consolidation, and enforces strict anti-poisoning guardrails against sensitive customer locations and warehouse floor security data.

## Technical Context

**Language/Version**: Python 3.14+ (monorepo backend standard in `services/api/pyproject.toml`)

**Primary Dependencies**:
- `fastapi>=0.141.1`, `pydantic>=2.13.5` (API presentation & deterministic serialization)
- `langgraph>=1.2.22`, `langgraph-checkpoint>=4.3.2` (Agent workflow state machine)
- `tinydb>=4.9.0` / `redis>=5.0.0` (Persistent agent memory backend isolated from vector store)
- `qdrant-client>=1.13.0` (Static knowledge base, strictly read-only for agent memory)
- `uv` (Package management per FR-002)

**Storage**:
- Dedicated agent memory storage: `TinyDBAgentMemoryRepository` / `RedisAgentMemoryRepository` managing `agent_memory` and `memory_audit_logs`.
- Strictly isolated from Qdrant vector database (`trackflow_knowledge`).

**Testing**: `pytest>=9.1.1`, `pytest-cov>=6.0.0` with unit, integration, and contract test suites in `services/api/tests/`.

**Target Platform**: Linux / Windows containerized FastAPI microservice (`services/api/`).

**Project Type**: Backend service extension within hexagonal monorepo architecture.

**Performance Goals**:
- Candidate memory proposal generation in single turn with < 100ms average overhead (SC-002).
- Cross-session memory recall lookup latency < 20ms.

**Constraints**:
- Zero write operations to Qdrant static knowledge (`trackflow_knowledge`) (SC-005).
- Single pending proposal queue limit (at most 1 active proposal per session/thread) (FR-012).
- Zero percent (0%) leaks of sensitive locations, warehouse floor paths, or commercial contracts (SC-004).
- Safe default: discard on ambiguity, silence, or topic shifts (FR-013).

**Scale/Scope**:
- 8 logistics carriers across 2 primary operational regions (Zaragoza, Spain and Los Angeles, USA).
- 15 support specialists and coordinators across shifts.
- Maximum 20 consolidated active constraints per carrier-country profile.
- 14-day default TTL for transient recurring incident contexts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Rule | Compliance Status | Analysis & Safeguards |
|---|---|---|
| **I. Service Boundaries & Domain Isolation** | **PASSED** | Hexagonal architecture strictly preserved: domain entities in `domain/agent/`, ports in `domain/agent/ports.py`, orchestration in `application/services/`, persistence adapters in `infrastructure/persistence/`, and endpoints in `presentation/api/v1/agent.py`. No cross-boundary leaks. |
| **II. Public API Compatibility & Contract Serialization** | **PASSED** | All new memory endpoints declare explicit Pydantic `response_model` specifications, inject dependencies via FastAPI `Depends`, execute non-blocking operations via `run_in_threadpool`, and project data through dedicated response DTOs. |
| **III. Strict TypeScript & Static Type Safety** | **PASSED** | Monorepo type rules satisfied; Python backend maintains 100% type annotations and Pydantic validation models across all domain boundaries. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | **PASSED** | Handlers catch internal exceptions and return sanitized error schemas (`SanitizedErrorResponse`) with zero raw stack traces or internal paths exposed. PII, end-consumer addresses, and warehouse routes are filtered before persistence. |
| **VI. Test-First Development & Verification Gates** | **PASSED** | Full test coverage planned across unit tests (guardrails, classification, consolidation) and integration tests (lifecycle, cross-session recall, storage isolation). |
| **VII. Vector DB & Qdrant Persistence Isolation** | **PASSED** | Memory storage is strictly encapsulated within dedicated persistence adapters (`AgentMemoryRepositoryPort`). Vector store (`trackflow_knowledge`) remains 100% read-only. Zero writes target Qdrant. |

## Project Structure

### Documentation (this feature)

```text
specs/029-agent-memory-self-improvement/
├── plan.md              # This implementation plan
├── research.md          # Phase 0 architectural decisions & trade-off analysis
├── data-model.md        # Phase 1 domain entities, schemas, and state transitions
├── quickstart.md        # Phase 1 runnable validation scenarios
├── contracts/           # Phase 1 API and interface contracts
│   ├── agent-memory-api.yaml  # OpenAPI 3.1 specification for memory REST endpoints
│   └── memory-ports.md        # Python abstract repository & classifier port contracts
└── tasks.md             # Phase 2 output (generated by /speckit-tasks)
```

### Source Code (repository root)

```text
services/api/
├── domain/
│   └── agent/
│       ├── entities.py           # Extended with MemoryProposal, PersistentMemoryRecord, ConsolidatedCarrierProfile, etc.
│       ├── exceptions.py         # MemoryNotFoundError, MemoryGuardrailViolationError
│       └── ports.py              # AgentMemoryRepositoryPort, MemoryAuditLogRepositoryPort, MemoryGuardrailPort, UserIntentClassifierPort
├── application/
│   └── services/
│       ├── agent_workflow.py     # Extended LangGraph workflow (memory intake/recall, single-call proposal emission)
│       ├── support_agent_service.py # Wires memory repositories and coordinates proposal lifecycle
│       ├── memory_service.py     # Application service coordinating memory consolidation, recall, and lifecycle
│       └── memory_guardrails.py  # Anti-poisoning & sensitive location filtering rules
├── infrastructure/
│   └── persistence/
│       └── tinydb/
│           ├── agent_memory_repository.py      # Dedicated TinyDB adapter for persistent memories
│           └── memory_audit_log_repository.py  # Dedicated TinyDB adapter for immutable audit records
├── presentation/
│   ├── api/
│   │   └── v1/
│   │       ├── agent.py          # Updated with memory proposal in query response & feedback endpoints
│   │       └── memory.py         # Carrier profile & audit log inspection endpoints
│   ├── dependencies.py           # Dependency injection providers for memory ports
│   └── schemas/
│       └── agent.py              # Pydantic schemas for proposals, carrier profiles, and audit entries
└── tests/
    ├── unit/
    │   ├── test_memory_guardrails.py       # Anti-poisoning & sensitive data exclusion tests
    │   ├── test_intent_classification.py   # Explicit intent & safe default discard tests
    │   └── test_memory_consolidation.py    # Deduplication and carrier-country profile consolidation
    └── integration/
        ├── test_agent_memory_lifecycle.py  # End-to-end proposal -> approve/reject -> continuation
        └── test_memory_storage_isolation.py# Verification that Qdrant is 100% read-only & untouched
```

**Structure Decision**: Hexagonal modular layout within `services/api/`, preserving the single-agent LangGraph workflow while isolating memory persistence and guardrails behind domain ports.

## Complexity Tracking

> **Constitution Check passed with zero violations.** No temporary exceptions or architectural waivers required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | N/A |
