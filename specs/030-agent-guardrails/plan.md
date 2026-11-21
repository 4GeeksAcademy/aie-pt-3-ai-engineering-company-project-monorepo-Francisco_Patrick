# Implementation Plan: Agent Harnessing & Guardrails (Part 2 of 2)

**Branch**: `feature/agent-guardrails` (`030-agent-guardrails`) | **Date**: 2026-11-21 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/030-agent-guardrails/spec.md)

**Input**: Feature specification from `specs/030-agent-guardrails/spec.md`

## Summary

Harden TrackFlow's frontline Customer Experience (CX) LangGraph Support Agent (from Milestone 8 Part 1) with multi-layered defense-in-depth guardrails across US (Los Angeles) and Spain (Zaragoza) B2B/B2C operations (`trackflow-BRIEFING.es.md`). The implementation preserves the existing single-agent 7-node LangGraph workflow and persistent operational memory while introducing four decoupled guardrail layers behind abstract domain ports:
1. **Input & Domain Scope Guardrail (`InputGuardrailPort`)**: Enforces immutable system authority (`security` anti-jailbreak across bilingual/rephrased variants), blocks unrelated personal tasks (`content` essays, homework, coding, therapy), permits brief small talk and general logistics trivia only with a mandatory redirect back to TrackFlow's logistics services (`content`), and enforces US vs. Spain country-policy separation (`content`).
2. **Session-Scoped Order & Policy Authorization Guardrail (`AuthorizationGuardrailPort`)**: Validates order/tracking inquiries against `AuthenticatedSessionContext`, rejecting cross-session lookups (e.g., Order `#45821`) with explicit lack-of-authorization refusals (`security`/`content`) and resolving authoritative country jurisdiction (`US` vs. `ES`) from order metadata, fulfillment location, or session operating country.
3. **Two-Tier Context & Tool Sanitizer (`ContextSanitizerPort`)**: Isolates external RAG chunks and operational tool outputs (`ticket_tool`, `inventory_tool`) by stripping/neutralizing embedded imperative directives while wrapping factual content in passive `<external_context>` delimiters (Tier 1), or quarantining/aborting purely adversarial payloads (Tier 2), logging a `security` event in both cases.
4. **Post-Generation Output Guardrail (`OutputGuardrailPort`)**: Validates candidate responses for expected structure (`structural`), system prompt leakage (`security`), and restricted corporate/customer data (`content`/`security`: cross-session orders, negotiated UPS/FedEx/DHL/MRW/SEUR carrier rates, B2B contract terms, and internal warehouse locations/routes), while appending mandatory TrackFlow redirections on casual/trivia turns and coordinating with Part 1 memory to suppress new proposals on blocked/redirected turns and discard pending proposals on blocked turns.
5. **Minimal Observability & Deterministic Verification (`GuardrailObservabilityPort`)**: Records structured `GuardrailAuditEvent` entries with masked/redacted preview snippets and exposes aggregated trigger counts (`GuardrailSummaryReport`) via both `GET /api/v1/agent/guardrails/summary` and a CLI/programmatic helper (`python -m application.services.guardrail_observability`).

## Technical Context

**Language/Version**: Python 3.14+ (monorepo backend standard in `services/api/pyproject.toml`)

**Primary Dependencies**:
- `fastapi>=0.141.1`, `pydantic>=2.13.5` (REST endpoints, dependency injection, and deterministic DTO serialization)
- `langgraph>=1.2.22`, `langgraph-checkpoint>=4.3.2` (Existing single-agent 7-node workflow state machine)
- `tinydb>=4.9.0` (Existing persistent memory & optional audit persistence)
- `qdrant-client>=1.13.0` (Read-only static knowledge base `trackflow_knowledge`)
- `uv` (Workspace package manager per FR-002; zero unapproved third-party guardrail dependencies required)

**Storage**:
- Thread-safe in-memory and optional TinyDB-backed `GuardrailAuditRegistry` storing `GuardrailAuditEvent` records with PII, restricted data, and system prompt fragments masked.
- Existing `TinyDBAgentMemoryRepository` and `TinyDBMemoryAuditLogRepository` from Part 1 (`029-agent-memory-self-improvement`).
- Static Qdrant vector collection (`trackflow_knowledge`) remains 100% read-only.

**Testing**: `pytest>=9.1.1`, `pytest-cov>=6.0.0` with offline deterministic unit, integration, and contract test suites in `services/api/tests/` using fixed fixtures and mocks (< 30s execution time per SC-006).

**Target Platform**: Linux / Windows containerized FastAPI microservice (`services/api/`).

**Project Type**: Backend service security & harnessing extension within a hexagonal monorepo architecture.

**Performance Goals**:
- Total guardrail evaluation overhead (input + authorization + context sanitization + output validation) < 15ms per turn.
- Full offline deterministic guardrail test suite execution < 30 seconds (SC-006).

**Constraints**:
- Preserve existing single-agent 7-node LangGraph topology (`intake`, `ticket_tool`, `inventory_tool`, `retrieval`, `tool_fallback`, `generation`, `refusal`) and Part 1 memory capabilities without creating a parallel agent (FR-001).
- Zero percent (0%) leakage of cross-session orders (`#45821`), negotiated carrier rates (UPS, FedEx, DHL, MRW, SEUR), B2B commercial terms, warehouse physical locations/routes, or internal system prompt instructions (SC-004).
- Suppress new memory proposals on any blocked or casual-redirected turn; discard active pending memory proposals when a turn triggers a guardrail block (FR-001).
- Bilingual enforcement across Spanish and English inputs and outputs.

**Scale/Scope**:
- 2 operational jurisdictions (`US` - Los Angeles, `ES` - Zaragoza/Madrid) across B2B and B2C customer segments.
- 4 distinct defense-in-depth guardrail layers (`input_guard`, `authorization_guard`, `context_sanitizer`, `output_guard`).
- 3 standardized failure classifications (`structural`, `content`, `security`).
- At least 3 distinct jailbreak rephrasings plus all 4 mandatory TrackFlow briefing scenarios documented and deterministically tested.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Rule | Compliance Status | Analysis & Safeguards |
|---|---|---|
| **I. Service Boundaries & Domain Isolation** | **PASSED** | Hexagonal architecture strictly preserved within `services/api/`: domain entities in `domain/agent/entities.py`, abstract ports in `domain/agent/ports.py`, guardrail orchestration in `application/services/agent_guardrails.py` and `guardrail_observability.py`, and FastAPI routes in `presentation/api/v1/agent.py`. |
| **II. Public API Compatibility & Contract Serialization** | **PASSED** | `POST /api/v1/agent/query` maintains full backward compatibility (new `session_context` request field and `guardrail_interventions` response field are optional with safe defaults). New `GET /api/v1/agent/guardrails/summary` declares explicit `GuardrailSummaryResponseSchema`, injects dependencies via `Depends`, and runs via `run_in_threadpool`. |
| **III. Strict TypeScript & Static Type Safety** | **PASSED** | Python backend modules maintain 100% explicit type annotations, `TypedDict` state contracts, frozen `@dataclass` entities, and Pydantic v2 validation schemas across all boundaries. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | **PASSED** | All `GuardrailAuditEvent` preview snippets are sanitized to mask PII, email addresses, restricted carrier rates, warehouse routes, and system prompt fragments (`FR-011`). Output guardrails fail closed with sanitized fallback messages and zero raw stack traces. |
| **VI. Test-First Development & Verification Gates** | **PASSED** | Deterministic offline test suite (`test_agent_guardrails_input.py`, `test_agent_guardrails_output.py`, `test_agent_guardrails_context_isolation.py`, `test_agent_guardrails_e2e.py`) runs with fixed fixtures/mocks and fails the build if any abusive input passes (`FR-013`, `SC-006`). |
| **VII. Vector DB & Qdrant Persistence Isolation** | **PASSED** | `trackflow_knowledge` remains strictly read-only. Retrieved chunks pass through `ContextSanitizerPort` in the application layer after retrieval via `VectorStorePort`, never mutating Qdrant points. |

## Project Structure

### Documentation (this feature)

```text
specs/030-agent-guardrails/
├── plan.md              # This implementation plan
├── research.md          # Phase 0 architectural decisions & defense-in-depth design
├── data-model.md        # Phase 1 domain entities, schemas, and state transitions
├── quickstart.md        # Phase 1 deterministic runnable validation scenarios
├── contracts/           # Phase 1 API and domain port contracts
│   ├── agent-guardrails-api.yaml # OpenAPI 3.1 specification for query & guardrail summary endpoints
│   └── guardrail-ports.md        # Python abstract guardrail & observability port contracts
└── tasks.md             # Phase 2 output (generated by /speckit-tasks)
```

### Source Code (repository root)

```text
services/api/
├── domain/
│   └── agent/
│       ├── entities.py                  # Extended with AuthenticatedSessionContext, GuardrailEvaluationResult, GuardrailAuditEvent, GuardrailSummaryReport
│       ├── exceptions.py                # Extended with GuardrailBlockedError, UnauthorizedOrderAccessError
│       └── ports.py                     # Extended with InputGuardrailPort, AuthorizationGuardrailPort, ContextSanitizerPort, OutputGuardrailPort, GuardrailObservabilityPort
├── application/
│   └── services/
│       ├── agent_guardrails.py          # Multi-layered guardrail implementations (Input, Authorization/Country Policy, Two-Tier Context Sanitizer, Output Validator, System Prompt Builder)
│       ├── guardrail_observability.py   # GuardrailAuditRegistry, redaction/masking helper, and CLI summary runner
│       ├── agent_workflow.py            # Integrates input/auth guards in intake_node, context sanitizer in retrieval/tool nodes, output guard & memory coordination in generation/refusal nodes
│       ├── support_agent_service.py     # Wires guardrail ports & observability registry into compiled workflow and query execution
│       └── memory_service.py            # Supports discarding pending proposal on guardrail block and suppressing proposals on blocked/redirected turns
├── infrastructure/
│   └── adapters/
│       └── grounded_generation_adapter.py # Updated system instruction builder with immutable authority boundaries & passive data delimiter rules
├── presentation/
│   ├── api/
│   │   └── v1/
│   │       └── agent.py                 # Updated POST /query with optional session_context & guardrail metadata; added GET /guardrails/summary
│   ├── dependencies.py                  # Dependency injection providers for guardrail validators and observability registry
│   └── schemas/
│       └── agent.py                     # Pydantic schemas for AuthenticatedSessionContextSchema, GuardrailSummaryResponseSchema, GuardrailInterventionSchema
└── tests/
    ├── unit/
    │   ├── test_agent_guardrails_input.py             # Jailbreak variants (>=3), personal task refusal, casual trivia redirection, country policy mixing
    │   ├── test_agent_guardrails_authorization.py     # Session-scoped order ownership (#45821), fail-closed missing session, country resolution
    │   ├── test_agent_guardrails_context_isolation.py # Two-tier RAG & tool prompt-injection neutralization vs quarantine
    │   └── test_agent_guardrails_output.py            # Restricted data leak prevention (carrier rates, warehouse routes, B2B terms, system prompt, malformed output)
    └── integration/
        └── test_agent_guardrails_observability.py     # End-to-end LangGraph guardrail flow, memory proposal suppression/discard, and GET /api/v1/agent/guardrails/summary verification
```

**Structure Decision**: Extend the existing hexagonal modular layout inside `services/api/`, embedding defense-in-depth guardrail ports directly into the 7-node LangGraph workflow (`agent_workflow.py`) and `SupportAgentService` so the single frontline CX agent from Part 1 is hardened in place without introducing a parallel agent or breaking existing public API contracts.

## Complexity Tracking

> **Constitution Check passed with zero violations.** No temporary exceptions or architectural waivers required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | N/A |
