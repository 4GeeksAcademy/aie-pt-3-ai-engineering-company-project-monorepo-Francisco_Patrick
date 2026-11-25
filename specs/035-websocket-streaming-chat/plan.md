# Implementation Plan: Real-Time Bidirectional WebSocket Streaming Chat with True Generation Abort (Part 2 of 2)

**Branch**: `035-websocket-streaming-chat` | **Date**: 2026-11-24 | **Spec**: [specs/035-websocket-streaming-chat/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/035-websocket-streaming-chat/spec.md)

**Input**: Feature specification from `/specs/035-websocket-streaming-chat/spec.md`

---

## Summary

Upgrade the TrackFlow Support Agent interaction from a synchronous request-response cycle (`POST /api/v1/agent/query`) to a real-time, full-duplex WebSocket streaming chat channel (`/api/v1/agent/ws` and legacy `/agent/ws`) hosted in the backoffice `/knowledge` Support Agent view, enabling live token-by-token response rendering, true mid-stream server-side generation abort (`interrupt` and mid-stream redirection), JWT authentication with per-user thread ownership binding, and automatic progressive-backoff reconnection with full thread rehydration.

The technical approach combines:
1. **Decoupled Pub/Sub Event Bus & Cooperative Generation Abort (`services/api/`)**: An abstract `AgentChatEventBrokerPort` (`services/api/domain/agent/ports.py`) implemented by an async-safe and thread-safe `AgentChatEventBroker` (`services/api/infrastructure/messaging/agent_chat_event_broker.py`). The broker manages per-thread subscriber queues (`asyncio.Queue`), active generation `asyncio.Task` handles, and cooperative `abort_event` signals, publishing named structured events (`session_rehydrated`, `generation_started`, `token_chunk`, `generation_interrupted`, `generation_completed`, `error`, `pong`) strictly aligned with TrackFlow's support agent domain conventions (zero leakage of Part 1's `rfp_ticket_created` SSE schema).
2. **Real-Time Streaming Workflow & Guardrail Sequencing (`SupportAgentService`)**: Extends `SupportAgentService` with an asynchronous streaming execution path (`stream_query`) that runs Layer 1 Input Guardrails, Layer 2 Authorization Guardrails, memory proposal resolution, and read-only operational tools/RAG retrieval (with Layer 3 Context Sanitizer) prior to streaming incremental `token_chunk` events, checks for cooperative cancellation before every chunk emission, and validates the accumulated text through Layer 4 Output Guardrails (`OutputGuardrailPort.validate_output`) before emitting `generation_completed`. When an `interrupt`, redirecting `user_message`, or last-subscriber disconnect occurs mid-generation, the active task cancels within `< 250ms`, emits `generation_interrupted` with `0` subsequent `token_chunk` events, and persists the partial assistant response with `status="interrupted"`.
3. **Dual In-Memory + Durable TinyDB Thread History Persistence (`services/api/infrastructure/adapters/`)**: Implements `AgentChatThreadRepositoryPort` via `TinyDBAgentChatThreadRepository` (`services/api/infrastructure/adapters/tinydb_chat_thread_repository.py`) to mirror conversation turns (`user`, `completed`, and `interrupted` assistant messages), thread owner identity (`owner_user_id`), and checkpoint references so thread rehydration (`session_rehydrated` and `GET /api/v1/agent/threads/{thread_id}/history`) survives both transient socket drops and server restarts.
4. **Interactive Backoffice Streaming Chat UI (`uis/backoffice/`)**: Upgrades `uis/backoffice/app/knowledge/page.tsx` with `useSupportAgentChat`, `supportAgentChatClient.ts`, and `SupportAgentChatPanel.tsx` (while retaining optional synchronous fallback), providing progressive live token rendering, mid-response **"Interrupt / Stop"** and instant redirection, preserved `interrupted` partial message badges, progressive exponential backoff reconnection (`1s, 2s, 4s, 8s, 16s, cap 30s`, halting on `4001`/`4003`), and rich turn metadata cards (citations, tool calls, memory proposals, and guardrail badges).

---

## Technical Context

**Language/Version**: Python 3.14 (`services/api/`), TypeScript 5.9 (`packages/shared/`, `uis/backoffice/`)  
**Primary Dependencies**:
- Backend: `fastapi>=0.141.1` (`WebSocket`, `WebSocketDisconnect`, `Depends`, `APIRouter`), `langgraph` (`CompiledStateGraph`, `MemorySaver`), `tinydb` (`TinyDB`, `MemoryStorage`), `pydantic>=2.13.5`, `python-jose`
- Frontend: `next@^14.2.5`, `react@^18.3.1`, native browser `WebSocket` API
- Shared Contracts: `@repo/shared-types` (`packages/shared/types/knowledge.ts`)  
**Storage**: Dual in-memory `AgentChatEventBroker` + LangGraph `MemorySaver` checkpointer mirrored to durable `TinyDBAgentChatThreadRepository` (`services/api/infrastructure/adapters/tinydb_chat_thread_repository.py`) and existing `TinyDBAgentMemoryRepository` / Qdrant `trackflow_knowledge` vector store  
**Testing**: `pytest` (`services/api/tests/test_websocket_streaming_chat.py` + existing `test_support_agent*.py` and `test_agent_*.py` regression suites), Jest / React Testing Library (`uis/backoffice/__tests__/supportAgentChat.test.ts`), `npm run typecheck`  
**Target Platform**: Linux container / Windows development environment, modern evergreen web browsers  
**Project Type**: Full-Stack Monorepo Web Service (`services/api`) & Next.js Backoffice UI (`uis/backoffice`)  
**Performance Goals**:
- True server-side generation abort latency `< 250ms` (target `< 20ms` in-process task cancellation) with `0` trailing `token_chunk` events after `generation_interrupted` (SC-003)
- Progressive first-token streaming prior to full response completion across 100% of multi-token turns (SC-001)
- Backoffice Core Web Vitals maintained (LCP ≤ 1.0s, TBT ≤ 200ms, CLS = 0)  
**Constraints**:
- Strict domain field alignment with TrackFlow's Support Agent (`session_id`, `thread_id`, `trace_id`, `turn_id`, `sources`, `sources_consulted`, `tool_calls`, `memory_proposal`, `guardrail_interventions`, `resolved_country`); zero leakage of Part 1's RFP `Ticket` SSE notification schema (`rfp_ticket_created`, `rfp_id`, `services_requested`) (FR-013, SC-006)
- Strict per-user thread ownership binding via backoffice JWT (`owner_user_id`), rejecting unauthenticated clients (`4001`) and cross-user thread access (`4003` / HTTP `403`)
- Strict TypeScript (`strict: true`, zero `any`, explicit return types, JSDoc comments, `import type`)  
**Scale/Scope**: Full-duplex multi-turn streaming conversations for concurrent backoffice operators across US and Spain support queues, backed by decoupled pub/sub thread channels and durable thread history persistence

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Requirement | Pre-Research Status | Post-Design Status | Verification Mechanism |
|---|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Frontends in `uis/`, backend in `services/api/` with hexagonal boundaries (`domain/`, `application/`, `infrastructure/`, `presentation/`), persistence adapters in `services/api/infrastructure/adapters/`, shared DTOs in `packages/shared/`. | **PASSED** | **PASSED** | `AgentChatEventBrokerPort` and `AgentChatThreadRepositoryPort` are defined in `services/api/domain/agent/ports.py`; persistence adapter lives in `services/api/infrastructure/adapters/tinydb_chat_thread_repository.py`; pub/sub broker lives in `services/api/infrastructure/messaging/agent_chat_event_broker.py`; shared DTOs live in `packages/shared/types/knowledge.ts`. |
| **II. Public API Compatibility & Strict Contract Serialization** | Explicit Pydantic `response_model` / OpenAPI schemas, `Depends` injection, non-blocking async execution, DTO projections, dual `/api/v1/*` and legacy route compatibility. | **PASSED** | **PASSED** | `GET /api/v1/agent/threads/{thread_id}/history` declares `response_model=ChatThreadHistoryResponseSchema`; `/api/v1/agent/ws` uses typed Pydantic event schemas and non-blocking async task orchestration; `agent.router` is dual-mounted at `/api/v1/agent` and `/agent`, preserving `POST /api/v1/agent/query` with zero breaking changes. |
| **III. Strict TypeScript & Static Type Safety** | `strict: true`, zero `any`, no `@ts-ignore`, explicit return types, JSDoc comments, `import type`. | **PASSED** | **PASSED** | `packages/shared/types/knowledge.ts`, `uis/backoffice/lib/supportAgentChatClient.ts`, `uis/backoffice/hooks/useSupportAgentChat.ts`, and `uis/backoffice/components/knowledge/SupportAgentChatPanel.tsx` strictly satisfy workspace `tsconfig.json` flags with zero `any`. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw stack traces in 500s or WebSocket `error` frames, zero plaintext token/PII leaks in logs, no swallowed exceptions, resilient UI connection states. | **PASSED** | **PASSED** | WebSocket errors emit sanitized `ServerErrorEvent` payloads (`error_code`, `detail`); Layer 1–4 guardrails sanitize untrusted inputs and final accumulated outputs; UI surfaces connection badges and actionable reconnect/fallback controls. |
| **V. Performance-First Architecture & Core Web Vitals** | LCP ≤ 1.0s, TBT ≤ 200ms, CLS = 0. Non-blocking SSR hydration. | **PASSED** | **PASSED** | WebSocket handshake initiates asynchronously inside a client `useEffect` after initial render, never blocking initial SSR paint or LCP, and renders streamed tokens incrementally without layout shift. |
| **VI. Test-First Development & Deterministic Verification Gates** | Automated unit/integration coverage (`pytest`, `jest`, `npm run typecheck`, `npm run build`). | **PASSED** | **PASSED** | Dedicated `pytest` suite (`test_websocket_streaming_chat.py`) and Jest suite (`supportAgentChat.test.ts`) verify streaming, abort, auth, ownership, backoff, and rehydration deterministically alongside all existing agent test suites. |
| **VII. Vector Database & Qdrant SDK Governance** | Encapsulated vector adapters, 0.62 similarity threshold, verifiable citations, graceful degradation. | **PASSED** | **PASSED** | Reuses the existing `SupportAgentService` and `QdrantVectorStoreAdapter` via `VectorStorePort` with the calibrated `0.62` threshold and returns verifiable `sources` citations in `generation_completed`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/035-websocket-streaming-chat/
├── spec.md                                         # Feature specification
├── plan.md                                         # This file (/speckit-plan output)
├── research.md                                     # Phase 0 architectural decisions & trade-offs
├── data-model.md                                   # Phase 1 domain entities, pub/sub events & state machines
├── quickstart.md                                   # Phase 1 runnable validation & verification guide
├── contracts/                                      # Phase 1 API & WebSocket event contracts
│   ├── websocket-chat-api.yaml                     # OpenAPI 3.1 contract for WebSocket & thread history REST API
│   └── websocket-chat-events.schema.json           # JSON Schema for discriminated client & server WebSocket frames
└── tasks.md                                        # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
packages/shared/
└── types/
    └── knowledge.ts                                # Extended with Support Agent WebSocket chat DTOs (ChatMessageDTO, ChatThreadHistoryResponseDTO, AgentChatStreamEventDTO, AgentChatClientCommandDTO, WebSocketChatConnectionStatus, and AgentQueryResponseDTO)

services/api/
├── domain/
│   └── agent/
│       ├── entities.py                             # Extended with ChatMessage, ChatThreadState, AgentChatStreamEvent, and ChatTurnStatus domain entities
│       └── ports.py                                # Extended with AgentChatEventBrokerPort and AgentChatThreadRepositoryPort interfaces
├── application/
│   └── services/
│       └── support_agent_service.py                # Extended with async stream_query / cooperative cancellation & thread rehydration orchestration
├── infrastructure/
│   ├── adapters/
│   │   └── tinydb_chat_thread_repository.py        # Thread-safe TinyDB persistence adapter implementing AgentChatThreadRepositoryPort
│   └── messaging/
│       └── agent_chat_event_broker.py              # Async/thread-safe pub/sub broker managing per-thread subscriber queues, active generation tasks, and true task cancellation
├── presentation/
│   ├── api/v1/
│   │   └── agent.py                                # Added WebSocket /ws endpoint and GET /threads/{thread_id}/history REST endpoint
│   ├── dependencies.py                             # Added get_agent_chat_thread_repository_dep and get_agent_chat_event_broker_dep providers
│   └── schemas/
│       └── agent.py                                # Added ChatMessageSchema, ChatThreadHistoryResponseSchema, and typed WebSocket event schemas
└── tests/
    └── test_websocket_streaming_chat.py            # Automated pytest suite for WebSocket JWT auth (4001), thread ownership (4003), pub/sub token_chunk streaming, true generation abort (<250ms, 0 trailing chunks), redirect, disconnect cleanup, and durable rehydration

uis/backoffice/
├── app/
│   └── knowledge/
│       └── page.tsx                                # Upgraded to host real-time WebSocket Support Agent chat with optional synchronous fallback mode
├── components/
│   └── knowledge/
│       └── SupportAgentChatPanel.tsx               # Interactive streaming chat timeline with progressive token rendering, Interrupt/Stop button, Interrupted status badges, citation/tool/memory cards, and connection indicator
├── hooks/
│   └── useSupportAgentChat.ts                      # React hook managing WebSocket lifecycle, progressive backoff (1s..30s), live token accumulation, interrupt/redirect, and thread rehydration
├── lib/
│   └── supportAgentChatClient.ts                   # Typed WebSocket frame serializer/parser, backoff calculator, and turn deduplication/reconciliation utilities
└── __tests__/
    └── supportAgentChat.test.ts                    # Jest tests for progressive token chunk rendering, mid-response interrupt & preservation, redirect while streaming, exponential backoff, auth halt, and turn deduplication
```

**Structure Decision**: Preserves the TrackFlow monorepo hexagonal architecture across `services/api/` (`domain/agent/`, `application/services/`, `infrastructure/adapters/`, `infrastructure/messaging/`, `presentation/api/v1/`), shared contracts in `packages/shared/types/knowledge.ts`, and the backoffice frontend in `uis/backoffice/`.

---

## Complexity Tracking

> **No Constitution violations detected.** All gates pass without exceptions.
