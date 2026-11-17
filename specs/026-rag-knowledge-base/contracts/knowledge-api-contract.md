# Contract Specification: Knowledge Base & RAG Endpoints

**Feature Branch**: `026-rag-knowledge-base`  
**Date**: 2026-11-16  
**OpenAPI Spec**: [knowledge-api.yaml](file:///J:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/026-rag-knowledge-base/contracts/knowledge-api.yaml)

---

## 1. REST Endpoint Contracts

### 1.1. Query Knowledge Base
- **Method / Path**: `POST /api/v1/knowledge/query` (Legacy alias: `POST /knowledge/query`)
- **Controller**: `presentation.api.v1.knowledge.query_knowledge`
- **Dependency Injection**:
  - `knowledge_service: KnowledgeService = Depends(get_knowledge_service_dep)`
  - Current authenticated user: optional or via `Depends(get_current_user_dep)` (read-only access).
- **Request Body**:
  ```json
  {
    "query": "What is TrackFlow's standard return window and who covers return shipping costs?",
    "language": "en",
    "top_k": 3,
    "min_score": 0.62
  }
  ```
- **Response Model**: `KnowledgeQueryResponseSchema` (HTTP 200)
  ```json
  {
    "query": "What is TrackFlow's standard return window and who covers return shipping costs?",
    "answer": "TrackFlow's standard return window is 30 days from delivery, unless customized in the client contract. Return shipping costs are covered by the client brand under standard circumstances; TrackFlow covers shipping only in cases of transit damage or delivery error.",
    "is_refusal": false,
    "sources": [
      {
        "source_document": "returns-policy",
        "section": "Standard Return Window & Costs",
        "similarity_score": 0.86
      }
    ],
    "execution_time_ms": 115.4
  }
  ```
- **Error Responses**:
  - `HTTP 422 Unprocessable Entity`: Triggered when query is less than 3 characters, empty, or exceeds 1000 characters.
  - `HTTP 503 Service Unavailable`: Triggered when Qdrant connection is degraded or fails connection timeout.

### 1.2. Knowledge Base Health & Index Status
- **Method / Path**: `GET /api/v1/knowledge/health` (Legacy alias: `GET /knowledge/health`)
- **Controller**: `presentation.api.v1.knowledge.get_health`
- **Response Model**: `KnowledgeHealthResponseSchema` (HTTP 200)
  ```json
  {
    "status": "healthy",
    "collection_name": "trackflow_knowledge",
    "indexed_points_count": 12,
    "vector_dimensions": 384
  }
  ```

---

## 2. Environment Configuration Contract (`.env` & `.env.example`)

Per FR-016, FR-017, FR-018, and SC-007, the Knowledge Base & RAG runtime exposes an externalized environment variable contract in `services/api/.env` and `services/api/.env.example`:

```dotenv
# AI, LLM & Agent Runtime Configuration (RAG & Knowledge Base)
LLM_API_KEY=your_llm_api_key_here
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
AGENT_MODEL=gemini-2.5-pro

# Embedding & Vector Store Configuration
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
USE_FASTEMBED_ONNX=false
KNOWLEDGE_SIMILARITY_THRESHOLD=0.62
QDRANT_URL=
QDRANT_HOST=
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=trackflow_knowledge
```

### Security & Fallback Guarantees
1. **Zero Secret Leakage**: `LLM_API_KEY` is strictly prohibited from appearing in HTTP responses, error payloads, OpenAPI examples, or application logs.
2. **Deterministic Fallback**: When `LLM_API_KEY` is omitted, empty, or set to a template placeholder (`your_llm_api_key_here`), or when an external provider endpoint is unreachable, `GroundedGenerationAdapter` seamlessly executes deterministic grounded synthesis while enforcing all corporate guardrails.

---

## 3. Backward Compatibility & Dual Route Mounting

Per TrackFlow Monorepo Constitution Principle II (Public API Compatibility):
1. Routes are mounted under canonical versioned path `/api/v1/knowledge/*`.
2. Routes are also mounted under legacy alias path `/knowledge/*` in `services/api/main.py`.
3. 100% of endpoints declare explicit Pydantic `response_model` annotations.
4. Internal vector payloads, embeddings, secret credentials, and raw Qdrant `ScoredPoint` primitives are strictly isolated and never leaked across HTTP boundaries.

---

## 4. Frontend Contract Integration

The client interface in `uis/backoffice/app/knowledge/page.tsx` interacts with the backend using the shared TypeScript interfaces from `@repo/shared-types`:

- `KnowledgeQueryRequestDTO`
- `KnowledgeQueryResponseDTO`
- `KnowledgeSourceCitationDTO`

Client-side form submits via POST to `${NEXT_PUBLIC_API_URL}/api/v1/knowledge/query` with timeout handling and automatic retry CTAs.
