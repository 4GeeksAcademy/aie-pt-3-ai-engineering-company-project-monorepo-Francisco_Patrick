# Implementation Plan: RAG & Knowledge Base

**Branch**: `026-rag-knowledge-base` | **Date**: 2026-11-16 | **Spec**: [spec.md](file:///J:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/026-rag-knowledge-base/spec.md)

**Input**: Feature specification from `specs/026-rag-knowledge-base/spec.md` and briefing from `docs/rag/trackflow-BRIEFING.en.md`.

---

## Summary

The commercial and frontline teams (Account Managers, Business Development, Operations Coordinators) need an AI assistant that answers questions about standard corporate policies (carrier coverage, returns, delivery SLAs, storage pricing) accurately in the authentic voice of TrackFlow sales, without hallucinations or unauthorized promises. Additionally, platform operators and developers require externalized environment configuration (`.env` and `.env.example`) to securely configure the LLM API key, select the desired LLM and agent models, and tune embedding and vector store settings without hardcoding credentials or modifying code.

This feature implements:
1. An idempotent ingestion pipeline that parses and semantically chunks all 4 corporate knowledge documents (`sla-delivery`, `returns-policy`, `carrier-coverage`, `storage-pricing`), generating at least 3 chunks per document (12 total) with deterministic UUID v5 identifiers.
2. A vector storage adapter encapsulating Qdrant (`qdrant-client`) adhering to Constitutional Rule VII under collection `trackflow_knowledge` with 384-dimensional cosine similarity.
3. An embedding adapter powered by `fastembed` (`BAAI/bge-small-en-v1.5` / `all-MiniLM-L6-v2`) and calibrated cross-lingual semantic features behind an abstract `EmbeddingServicePort`.
4. A calibrated similarity score threshold (`0.62`, configurable via `KNOWLEDGE_SIMILARITY_THRESHOLD`) that filters candidates and gracefully triggers standardized informational refusals for out-of-scope or ungrounded queries.
5. Strict business guardrails guaranteeing that volume storage discounts (>50 m³) mandate Miguel Torres's approval, peak season delivery times warn of SLA exemptions (+40% timeline), international returns require Sofía Ramos's manual handling, and carrier overrides require Carlos Vega's sign-off.
6. Externalized AI & Agent Runtime Configuration (`KnowledgeRuntimeConfig`) driven by `.env` and documented in `services/api/.env.example` (`LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `AGENT_MODEL`, `EMBEDDING_MODEL`, `USE_FASTEMBED_ONNX`, `KNOWLEDGE_SIMILARITY_THRESHOLD`, `QDRANT_URL`, `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION_NAME`), enforcing secret masking and providing resilient fallback to deterministic grounded synthesis when no live external API key is configured or when upstream model calls fail.
7. A dual-mounted FastAPI endpoint (`POST /api/v1/knowledge/query` and `POST /knowledge/query`) and an interactive, accessible Backoffice UI in `uis/backoffice/app/knowledge/page.tsx`.
8. An automated evaluation suite (`data/eval/test-queries.json` and `scripts/evaluate_rag_retrieval.py`) proving $\ge 80\%$ Recall@3.

---

## Technical Context

**Language/Version**: Python 3.14+ (Backend), TypeScript 5.5+ (Frontend & Shared Packages)  
**Primary Dependencies**:
- Backend: `fastapi>=0.141.1`, `pydantic>=2.13.5`, `qdrant-client>=1.13.0`, `fastembed>=0.5.0`, `httpx>=0.28.1`, `python-dotenv>=1.0.1`, `pytest>=9.1.1`
- Frontend: `next@14.2.5`, `react@18.3.1`, `tailwindcss@3.4.1`, `@repo/shared-types`  
**Storage**: Qdrant Vector Database (collection: `trackflow_knowledge`, Cosine distance, 384 dims); `:memory:` mode for tests and CI, external daemon on port 6333 (`QDRANT_HOST`/`QDRANT_PORT`/`QDRANT_URL`) for production.  
**Configuration (Environment Variables)**:
- AI & Agent Models: `LLM_API_KEY`, `LLM_PROVIDER` (default: `gemini` or `openai`), `LLM_MODEL` (default: `gemini-2.5-flash`), `AGENT_MODEL` (default: `gemini-2.5-pro`)
- Embeddings & Retrieval: `EMBEDDING_MODEL` (default: `BAAI/bge-small-en-v1.5`), `USE_FASTEMBED_ONNX` (default: `false`), `KNOWLEDGE_SIMILARITY_THRESHOLD` (default: `0.62`)
- Vector Store: `QDRANT_URL`, `QDRANT_HOST`, `QDRANT_PORT` (default: `6333`), `QDRANT_COLLECTION_NAME` (default: `trackflow_knowledge`)  
**Testing**: `pytest` for backend unit/integration tests; Jest/React Testing Library for frontend UI tests; `scripts/evaluate_rag_retrieval.py` for Recall@3 evaluation.  
**Target Platform**: Linux containers (`services/Dockerfile`), Windows local dev, Modern Web Browsers (Chrome, Firefox, Safari).  
**Project Type**: Monorepo Web Application (FastAPI backend + Next.js App Router frontend + Shared TypeScript package).  
**Performance Goals**:
- End-to-end query response time $\le 3.5$ s (SC-004), typically $<150$ ms in local/deterministic mode.
- Retrieval Recall@3 $\ge 80\%$ on standardized evaluation queries (SC-002).
- Backoffice UI Core Web Vitals: LCP $\le 1.0$ s, TBT $\le 200$ ms, CLS $= 0$.  
**Constraints**:
- Strictly zero hallucinations: out-of-scope queries must trigger refusal (SC-001, SC-003).
- Zero `any` in TypeScript; explicit Pydantic response models in FastAPI.
- Absolute adherence to corporate governance rules (Miguel Torres, Sofía Ramos, Carlos Vega, peak season warning).
- Zero plaintext API key leakage in source code, logs, exceptions, or HTTP responses (FR-018, SC-007).  
**Scale/Scope**: 4 canonical knowledge documents, 12 initial semantic chunks, frontline team of ~15-30 concurrent users, expandable to full corporate policy repository.

---

## Constitution Check

*GATE: Evaluated before Phase 0 research and re-evaluated post-design.*

| Principle | Requirement | Plan Status | Design Verification |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Monorepo architectural boundaries strictly preserved; frontend in `uis/` accesses backend strictly via HTTP REST; shared types in `packages/shared/`. | **PASS** | `uis/backoffice` consumes `/api/v1/knowledge/query` via fetch with types from `@repo/shared-types`. No cross-boundary database or file imports. |
| **II. Public API Compatibility & Strict Contract Serialization** | Explicit Pydantic `response_model`, FastAPI `Depends` for DI, async non-blocking execution, dual route mounting (`/api/v1/` and legacy), zero leaked internal primitives. | **PASS** | `KnowledgeQueryResponseSchema` declared on all endpoints; dependencies resolved via `get_knowledge_service_dep`; dual mounted in `main.py`; raw Qdrant objects and credentials never exposed. |
| **III. Strict TypeScript & Static Type Safety** | Zero `any`, `strict: true`, explicit return types, explicit type imports (`import type`), JSDoc comments. | **PASS** | `packages/shared/types/knowledge.ts` defined with strict DTO interfaces and re-exported. All UI components strictly typed. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw stack traces exposed in HTTP 500; zero PII/credentials logged; no swallowed exceptions; resilient UI error states with retry CTA. | **PASS** | `KnowledgeRuntimeConfig` masks `llm_api_key` in `repr`/`str`/logs; external LLM errors log sanitized messages and fall back to deterministic synthesis; Qdrant connection failures return HTTP 503; Backoffice UI provides user-visible error alert and retry button. |
| **V. Performance-First & Core Web Vitals** | Production builds maintain LCP $\le 1.0$s, TBT $\le 200$ms, CLS $= 0$; no hydration blocking spinners; modern JS baseline. | **PASS** | Knowledge UI uses lightweight server/client components with deferred client hydration, skeleton states, and zero layout shift. |
| **VI. Test-First & Deterministic Verification Gates** | Automated unit and integration tests; deterministic seeding; static analysis gates (`npm run typecheck`, `npm run build`, `pytest`). | **PASS** | Ingestion script uses deterministic UUID v5; Qdrant memory adapter allows isolated tests; benchmark script automated in CI. |
| **VII. Vector Database & Qdrant Governance** | Qdrant SDK encapsulated in `infrastructure/adapters/`; canonical collection `trackflow_knowledge`; deterministic UUID v5 IDs; calibrated similarity threshold; source citations; graceful degradation. | **PASS** | Encapsulated in `QdrantVectorStoreAdapter` under `VectorStorePort`; calibrated threshold `0.62` with refusal; source citations returned in payload. |

---

## Project Structure

### Documentation (this feature)

```text
specs/026-rag-knowledge-base/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output: decisions on Qdrant, embeddings, chunking, threshold, env config
├── data-model.md        # Phase 1 output: entities, runtime config model, value objects, schemas, DTOs
├── quickstart.md        # Phase 1 output: end-to-end runnable validation guide (including .env setup)
├── contracts/           # Phase 1 output: OpenAPI spec & contract documentation
│   ├── knowledge-api.yaml
│   └── knowledge-api-contract.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
packages/
└── shared/
    └── types/
        ├── knowledge.ts                     # TypeScript DTOs for Knowledge queries, citations, health
        └── index.ts                         # Re-exporting knowledge types

services/api/
├── .env.example                             # Documented environment template including AI/LLM/Agent/RAG vars
├── .env                                     # Local runtime environment configuration
├── domain/
│   └── knowledge/
│       ├── __init__.py
│       ├── entities.py                      # KnowledgeDocument, KnowledgeChunk, RetrievedContext, GroundedAnswer, KnowledgeRuntimeConfig
│       ├── ports.py                         # VectorStorePort, EmbeddingServicePort, LLMGenerationPort
│       └── exceptions.py                    # KnowledgeBaseUnavailableException, IngestionException
├── application/
│   └── services/
│       ├── __init__.py
│       ├── chunking.py                      # MarkdownSemanticChunker (preserving tables & clauses, >=3 chunks/doc)
│       ├── knowledge_service.py             # KnowledgeService orchestrating retrieval, threshold, & generation
│       └── guardrails.py                    # Business constraint validator (Miguel Torres, peak season, etc.)
├── infrastructure/
│   └── adapters/
│       ├── qdrant_vector_store_adapter.py   # Qdrant client implementation with env/memory/remote support
│       ├── embedding_adapter.py             # FastEmbed ONNX / semantic adapter configured via EMBEDDING_MODEL
│       └── grounded_generation_adapter.py   # Hybrid LLM / deterministic grounded synthesis engine with LLM_API_KEY, LLM_MODEL, AGENT_MODEL
├── presentation/
│   ├── api/
│   │   └── v1/
│   │       └── knowledge.py                 # FastAPI router for /api/v1/knowledge/query and /health
│   ├── schemas/
│   │   └── knowledge.py                     # Pydantic request and response schemas
│   └── dependencies.py                      # Dependency injection providers wired with KnowledgeRuntimeConfig
├── tests/
│   ├── unit/
│   │   ├── test_knowledge_chunking.py       # Unit tests for markdown semantic chunker
│   │   ├── test_knowledge_config.py         # Unit tests for KnowledgeRuntimeConfig env loading & secret masking
│   │   ├── test_knowledge_guardrails.py     # Unit tests for business rules & constraint enforcement
│   │   └── test_knowledge_service.py        # Unit tests for KnowledgeService orchestration & refusal
│   └── integration/
│       ├── test_qdrant_adapter.py           # Integration tests for QdrantVectorStoreAdapter
│       └── test_knowledge_routes.py         # Integration tests for FastAPI endpoints with TestClient
└── main.py                                  # Dual route mounting for knowledge router

scripts/
├── ingest_knowledge_base.py                 # CLI script to parse, chunk, and idempotently upsert into Qdrant
└── evaluate_rag_retrieval.py                # Benchmark script calculating Recall@3 against evaluation dataset

data/
└── eval/
    └── test-queries.json                    # Standardized 10-query benchmark dataset covering 4 docs + edge cases

uis/backoffice/
├── app/
│   └── knowledge/
│       └── page.tsx                         # Frontline interactive query page
├── components/
│   └── knowledge/
│       ├── KnowledgeQueryForm.tsx           # Accessible search form with input validation
│       ├── KnowledgeAnswerCard.tsx          # Rendered answer with citation badges & confidence status
│       └── KnowledgeStatusState.tsx         # Skeleton loading and error banner with retry CTA
└── __tests__/
    └── knowledge.test.tsx                   # UI unit/component tests for knowledge screen
```

**Structure Decision**: Monorepo Web Application with Hexagonal Architecture in `services/api/` (Domain $\to$ Application $\to$ Infrastructure $\to$ Presentation), environment-driven runtime configuration via `KnowledgeRuntimeConfig` and `.env`/`.env.example`, strict type sharing via `packages/shared/types/knowledge.ts`, and Next.js App Router presentation in `uis/backoffice/`.

---

## Complexity Tracking

*No constitutional violations identified. Architecture conforms strictly to all 7 principles of the TrackFlow Monorepo Constitution.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | N/A |
