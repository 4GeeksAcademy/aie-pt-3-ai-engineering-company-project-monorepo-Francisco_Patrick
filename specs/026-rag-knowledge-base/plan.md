# Implementation Plan: RAG & Knowledge Base

**Branch**: `026-rag-knowledge-base` | **Date**: 2026-11-16 | **Spec**: [spec.md](file:///J:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/026-rag-knowledge-base/spec.md)

**Input**: Feature specification from `specs/026-rag-knowledge-base/spec.md` and briefing from `docs/rag/trackflow-BRIEFING.en.md`.

---

## Summary

The commercial and frontline teams (Account Managers, Business Development, Operations Coordinators) need an AI assistant that answers questions about standard corporate policies (carrier coverage, returns, delivery SLAs, storage pricing) accurately in the authentic voice of TrackFlow sales, without hallucinations or unauthorized promises.

This feature implements:
1. An idempotent ingestion pipeline that parses and semantically chunks all 4 corporate knowledge documents (`sla-delivery`, `returns-policy`, `carrier-coverage`, `storage-pricing`), generating at least 3 chunks per document (12 total) with deterministic UUID v5 identifiers.
2. A vector storage adapter encapsulating Qdrant (`qdrant-client`) adhering to Constitutional Rule VII under collection `trackflow_knowledge` with 384-dimensional cosine similarity.
3. An embedding adapter powered by `fastembed` (`bge-small-en-v1.5` / `all-MiniLM-L6-v2`) behind an abstract `EmbeddingServicePort`.
4. A calibrated similarity score threshold (`0.62`) that filters candidates and gracefully triggers standardized informational refusals for out-of-scope or ungrounded queries.
5. Strict business guardrails guaranteeing that volume storage discounts (>50 m³) mandate Miguel Torres's approval, peak season delivery times warn of SLA exemptions (+40% timeline), international returns require Sofía Ramos's manual handling, and carrier overrides require Carlos Vega's sign-off.
6. A dual-mounted FastAPI endpoint (`POST /api/v1/knowledge/query` and `POST /knowledge/query`) and an interactive, accessible Backoffice UI in `uis/backoffice/app/knowledge/page.tsx`.
7. An automated evaluation suite (`data/eval/test-queries.json` and `scripts/evaluate_rag_retrieval.py`) proving $\ge 80\%$ Recall@3.

---

## Technical Context

**Language/Version**: Python 3.14+ (Backend), TypeScript 5.5+ (Frontend & Shared Packages)  
**Primary Dependencies**:
- Backend: `fastapi>=0.141.1`, `pydantic>=2.13.5`, `qdrant-client>=1.13.0`, `fastembed>=0.5.0`, `pytest>=9.1.1`
- Frontend: `next@14.2.5`, `react@18.3.1`, `tailwindcss@3.4.1`, `@repo/shared-types`  
**Storage**: Qdrant Vector Database (collection: `trackflow_knowledge`, Cosine distance, 384 dims); `:memory:` mode for tests and CI, external daemon on port 6333 for production.  
**Testing**: `pytest` for backend unit/integration tests; Jest/React Testing Library for frontend UI tests; `scripts/evaluate_rag_retrieval.py` for Recall@3 evaluation.  
**Target Platform**: Linux containers (`services/Dockerfile`), Windows local dev, Modern Web Browsers (Chrome, Firefox, Safari).  
**Project Type**: Monorepo Web Application (FastAPI backend + Next.js App Router frontend + Shared TypeScript package).  
**Performance Goals**:
- End-to-end query response time $\le 3.5$ s (SC-004), typically $<150$ ms.
- Retrieval Recall@3 $\ge 80\%$ on standardized evaluation queries (SC-002).
- Backoffice UI Core Web Vitals: LCP $\le 1.0$ s, TBT $\le 200$ ms, CLS $= 0$.  
**Constraints**:
- Strictly zero hallucinations: out-of-scope queries must trigger refusal (SC-001, SC-003).
- Zero `any` in TypeScript; explicit Pydantic response models in FastAPI.
- Absolute adherence to corporate governance rules (Miguel Torres, Sofía Ramos, Carlos Vega, peak season warning).  
**Scale/Scope**: 4 canonical knowledge documents, 12 initial semantic chunks, frontline team of ~15-30 concurrent users, expandable to full corporate policy repository.

---

## Constitution Check

*GATE: Evaluated before Phase 0 research and re-evaluated post-design.*

| Principle | Requirement | Plan Status | Design Verification |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Monorepo architectural boundaries strictly preserved; frontend in `uis/` accesses backend strictly via HTTP REST; shared types in `packages/shared/`. | **PASS** | `uis/backoffice` consumes `/api/v1/knowledge/query` via fetch with types from `@repo/shared-types`. No cross-boundary database or file imports. |
| **II. Public API Compatibility & Strict Contract Serialization** | Explicit Pydantic `response_model`, FastAPI `Depends` for DI, async non-blocking execution, dual route mounting (`/api/v1/` and legacy), zero leaked internal primitives. | **PASS** | `KnowledgeQueryResponseSchema` declared on all endpoints; dependencies resolved via `get_knowledge_service_dep`; dual mounted in `main.py`; raw Qdrant objects never exposed. |
| **III. Strict TypeScript & Static Type Safety** | Zero `any`, `strict: true`, explicit return types, explicit type imports (`import type`), JSDoc comments. | **PASS** | `packages/shared/types/knowledge.ts` defined with strict DTO interfaces and re-exported. All UI components strictly typed. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw stack traces exposed in HTTP 500; zero PII/credentials logged; no swallowed exceptions; resilient UI error states with retry CTA. | **PASS** | Domain exceptions mapped in `core/exceptions.py`; Qdrant connection failures return HTTP 503; Backoffice UI provides user-visible error alert and retry button. |
| **V. Performance-First & Core Web Vitals** | Production builds maintain LCP $\le 1.0$s, TBT $\le 200$ms, CLS $= 0$; no hydration blocking spinners; modern JS baseline. | **PASS** | Knowledge UI uses lightweight server/client components with deferred client hydration, skeleton states, and zero layout shift. |
| **VI. Test-First & Deterministic Verification Gates** | Automated unit and integration tests; deterministic seeding; static analysis gates (`npm run typecheck`, `npm run build`, `pytest`). | **PASS** | Ingestion script uses deterministic UUID v5; Qdrant memory adapter allows isolated tests; benchmark script automated in CI. |
| **VII. Vector Database & Qdrant Governance** | Qdrant SDK encapsulated in `infrastructure/adapters/`; canonical collection `trackflow_knowledge`; deterministic UUID v5 IDs; calibrated similarity threshold; source citations; graceful degradation. | **PASS** | Encapsulated in `QdrantVectorStoreAdapter` under `VectorStorePort`; calibrated threshold `0.62` with refusal; source citations returned in payload. |

---

## Project Structure

### Documentation (this feature)

```text
specs/026-rag-knowledge-base/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output: decisions on Qdrant, embeddings, chunking, threshold
├── data-model.md        # Phase 1 output: entities, value objects, schemas, DTOs
├── quickstart.md        # Phase 1 output: end-to-end runnable validation guide
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
├── domain/
│   └── knowledge/
│       ├── __init__.py
│       ├── entities.py                      # KnowledgeDocument, KnowledgeChunk, RetrievedContext, GroundedAnswer
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
│       ├── qdrant_vector_store_adapter.py   # Qdrant client implementation with memory/remote support
│       ├── embedding_adapter.py             # FastEmbed ONNX adapter with test fallback
│       └── grounded_generation_adapter.py   # Grounded synthesis engine adhering to sales persona & guardrails
├── presentation/
│   ├── api/
│   │   └── v1/
│   │       └── knowledge.py                 # FastAPI router for /api/v1/knowledge/query and /health
│   ├── schemas/
│   │   └── knowledge.py                     # Pydantic request and response schemas
│   └── dependencies.py                      # Dependency injection providers for knowledge service
├── tests/
│   ├── unit/
│   │   ├── test_knowledge_chunking.py       # Unit tests for markdown semantic chunker
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

**Structure Decision**: Monorepo Web Application with Hexagonal Architecture in `services/api/` (Domain $\to$ Application $\to$ Infrastructure $\to$ Presentation), strict type sharing via `packages/shared/types/knowledge.ts`, and Next.js App Router presentation in `uis/backoffice/`.

---

## Complexity Tracking

*No constitutional violations identified. Architecture conforms strictly to all 7 principles of the TrackFlow Monorepo Constitution.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | N/A |
