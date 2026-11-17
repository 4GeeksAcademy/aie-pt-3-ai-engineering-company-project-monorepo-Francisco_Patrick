# Data Model: RAG & Knowledge Base

**Feature Branch**: `026-rag-knowledge-base`  
**Date**: 2026-11-16  
**Status**: Completed  

---

## 1. Domain Entities & Value Objects

The RAG & Knowledge Base domain is structured around six primary entities and value objects:

```mermaid
classDiagram
    class KnowledgeDocument {
        +string id
        +string title
        +string source_file
        +string language
        +string version
        +List~string~ sections
    }

    class KnowledgeChunk {
        +UUID id
        +string company
        +string source_document
        +string section
        +string language
        +int chunk_index
        +string text
        +List~float~ vector
    }

    class QueryRequest {
        +string query
        +string language
        +int top_k
        +float min_score
    }

    class RetrievedContext {
        +KnowledgeChunk chunk
        +float similarity_score
        +int rank
    }

    class GroundedAnswer {
        +string query
        +string answer
        +bool is_refusal
        +List~SourceCitation~ sources
        +float execution_time_ms
    }

    class SourceCitation {
        +string source_document
        +string section
        +float similarity_score
    }

    class KnowledgeRuntimeConfig {
        +string llm_provider
        +string llm_model
        +string agent_model
        +string embedding_model
        +bool use_fastembed_onnx
        +float similarity_threshold
        +string qdrant_collection_name
        +bool has_live_llm_key()
        +dict to_sanitized_dict()
    }

    KnowledgeDocument "1" --> "*" KnowledgeChunk : decomposes into
    QueryRequest --> "*" RetrievedContext : retrieves
    RetrievedContext --> "1" KnowledgeChunk : references
    GroundedAnswer --> "*" SourceCitation : cites
    KnowledgeRuntimeConfig ..> GroundedAnswer : configures synthesis & threshold
```

---

## 2. Entity Specifications

### 2.1. `KnowledgeDocument`
Represents a source operational policy or service specification markdown file.

- **Attributes**:
  - `id` (`str`): Unique canonical slug (e.g. `"sla-delivery"`, `"returns-policy"`, `"carrier-coverage"`, `"storage-pricing"`).
  - `title` (`str`): Human-readable document title (e.g. `"Delivery SLA"`).
  - `source_file` (`str`): Relative file path within the repository (e.g. `"docs/company-knowledge-base/trackflow-sla-delivery.en.md"`).
  - `language` (`str`): ISO 639-1 language code (e.g. `"en"` or `"es"`).
  - `version` (`str`): Semantic version or file timestamp.
  - `raw_content` (`str`): Raw markdown text content.

### 2.2. `KnowledgeChunk`
An atomic, self-contained semantic segment of a `KnowledgeDocument` containing a cohesive policy clause, pricing tier, or operational guideline.

- **Attributes**:
  - `id` (`UUID`): Deterministic UUID v5 generated via `uuid.uuid5(uuid.NAMESPACE_DNS, f"trackflow:{source_document}:{chunk_index}")`.
  - `company` (`str`): Always `"trackflow"`.
  - `source_document` (`str`): Canonical document slug (`"sla-delivery"`, `"returns-policy"`, `"carrier-coverage"`, `"storage-pricing"`).
  - `section` (`str`): Title or subtitle of the source section from which the chunk originated.
  - `language` (`str`): ISO 639-1 code (`"en"`).
  - `chunk_index` (`int`): 0-indexed position within the parent document ($0, 1, 2, \dots$).
  - `text` (`str`): Semantic body text used for embedding and context assembly.
  - `vector` (`Optional[List[float]]`): Dense 384-dimensional floating point representation.

- **Validation Rules**:
  - `chunk_index` must be non-negative integer ($\ge 0$).
  - `text` must not be empty or whitespace (minimum length 20 characters).
  - Each source document must generate at least 3 distinct chunks ($\text{count} \ge 3$).
  - No splitting of dependent clauses, bullet lists, or rate schedules.

### 2.3. `QueryRequest`
User inquiry submitted from frontline interfaces or API consumers.

- **Attributes**:
  - `query` (`str`): Plain text inquiry (e.g. `"What is TrackFlow's standard return window?"`).
  - `language` (`Optional[str]`): Preferred response language (defaults to `"en"`).
  - `top_k` (`int`): Maximum candidate chunks to retrieve (defaults to `3`, range $[1, 10]$).
  - `min_score` (`Optional[float]`): Minimum similarity score threshold (defaults to `0.62`).

- **Validation Rules**:
  - `query` cannot be empty or whitespace; stripped length must be between 3 and 1000 characters.
  - `top_k` must be between 1 and 10.
  - `min_score` must be between 0.0 and 1.0.

### 2.4. `RetrievedContext`
Represents a scored candidate chunk returned from semantic vector search.

- **Attributes**:
  - `chunk` (`KnowledgeChunk`): Retrieved chunk entity with metadata.
  - `similarity_score` (`float`): Cosine similarity score in range $[-1.0, 1.0]$.
  - `rank` (`int`): Ordinal position in retrieved results (1, 2, 3...).

- **Filtering Rules**:
  - Only candidates with $\text{similarity\_score} \ge \text{min\_score}$ are retained for generation.
  - Candidate list is sorted descending by `similarity_score`.

### 2.5. `GroundedAnswer`
The final synthesized response delivered to the caller.

- **Attributes**:
  - `query` (`str`): Echoed sanitized input query.
  - `answer` (`str`): Synthesized natural language answer adopting TrackFlow account manager voice.
  - `is_refusal` (`bool`): `True` if query fell below similarity threshold or lacked documented evidence; `False` if grounded answer generated.
  - `sources` (`List[SourceCitation]`): List of cited source documents and sections.
  - `execution_time_ms` (`float`): End-to-end processing latency in milliseconds.

- **Business Constraint Validations**:
  - Storage volume discount: If query discusses discounts above 50 m³, answer must state requirement for Commercial Director Miguel Torres's approval.
  - Peak season delivery: If query discusses peak periods (Black Friday, Christmas, January Sales), answer must state standard SLAs are not guaranteed and times extend up to 40%.
  - International returns: If query discusses cross-border returns, answer must state process is manual under Sofía Ramos.
  - Carrier exceptions: If query discusses carrier exceptions, answer must state Carlos Vega's approval is required.

### 2.6. `KnowledgeRuntimeConfig` (AI & Agent Runtime Configuration)
Represents the externalized environment-driven configuration governing LLM credentials, LLM and agent model selection, embedding settings, retrieval similarity threshold, and vector store connection parameters (FR-016, FR-017, FR-018).

- **Attributes**:
  - `llm_api_key` (`Optional[str]`): Secret API key read from `LLM_API_KEY` (never included in `__repr__`, `__str__`, logs, or API responses).
  - `llm_provider` (`str`): AI provider identifier read from `LLM_PROVIDER` (defaults to `"gemini"`, supports `"gemini"`, `"openai"`, `"deterministic"`).
  - `llm_model` (`str`): Primary language model identifier for grounded answer synthesis read from `LLM_MODEL` (defaults to `"gemini-2.5-flash"`).
  - `agent_model` (`str`): Agent reasoning and workflow model identifier read from `AGENT_MODEL` (defaults to `"gemini-2.5-pro"`).
  - `embedding_model` (`str`): Vector embedding model identifier read from `EMBEDDING_MODEL` (defaults to `"BAAI/bge-small-en-v1.5"`).
  - `use_fastembed_onnx` (`bool`): Flag indicating whether to initialize ONNX Runtime weights via FastEmbed, read from `USE_FASTEMBED_ONNX` (defaults to `False`).
  - `similarity_threshold` (`float`): Calibrated minimum similarity threshold read from `KNOWLEDGE_SIMILARITY_THRESHOLD` (defaults to `0.62`, range $[0.0, 1.0]$).
  - `qdrant_url` (`Optional[str]`): Optional Qdrant server URL read from `QDRANT_URL`.
  - `qdrant_host` (`Optional[str]`): Optional Qdrant hostname read from `QDRANT_HOST`.
  - `qdrant_port` (`int`): Qdrant server port read from `QDRANT_PORT` (defaults to `6333`).
  - `qdrant_collection_name` (`str`): Canonical collection name read from `QDRANT_COLLECTION_NAME` (defaults to `"trackflow_knowledge"`).

- **Validation & Security Rules**:
  - Placeholder values for `LLM_API_KEY` (`""`, `"your_llm_api_key_here"`, `"changeme"`, `"none"`, `"null"`) are treated as unconfigured (`has_live_llm_key == False`), causing the runtime to use the deterministic grounded synthesis fallback without raising missing-credential errors.
  - `similarity_threshold` is clamped/validated within $[0.0, 1.0]$; invalid non-numeric environment strings safely fall back to `0.62`.
  - `__repr__()` and `to_sanitized_dict()` mask `llm_api_key` as `"***REDACTED***"` when set or `"<unconfigured>"` when unset, guaranteeing zero secret exposure in logs or exception messages (FR-018, SC-007).

---

## 3. Environment Variable Mapping (`services/api/.env` & `.env.example`)

| Environment Variable | Config Field | Default Value | Secret? | Purpose |
|---|---|---|---|---|
| `LLM_API_KEY` | `llm_api_key` | `your_llm_api_key_here` | **Yes** | Secret API key for external LLM/Agent provider; falls back to deterministic synthesis when unset or placeholder |
| `LLM_PROVIDER` | `llm_provider` | `gemini` | No | Target AI provider (`gemini`, `openai`, or `deterministic`) |
| `LLM_MODEL` | `llm_model` | `gemini-2.5-flash` | No | Language model identifier for RAG answer synthesis |
| `AGENT_MODEL` | `agent_model` | `gemini-2.5-pro` | No | Agent model identifier for complex policy & multi-step reasoning |
| `EMBEDDING_MODEL` | `embedding_model` | `BAAI/bge-small-en-v1.5` | No | Dedicated 384-d vector embedding model identifier |
| `USE_FASTEMBED_ONNX` | `use_fastembed_onnx` | `false` | No | Enables local ONNX Runtime inference blending |
| `KNOWLEDGE_SIMILARITY_THRESHOLD` | `similarity_threshold` | `0.62` | No | Calibrated minimum cosine similarity score threshold |
| `QDRANT_URL` | `qdrant_url` | *(empty)* | No | Full HTTP URL for external Qdrant instance |
| `QDRANT_HOST` | `qdrant_host` | *(empty)* | No | Hostname for external Qdrant instance (uses `:memory:` when empty) |
| `QDRANT_PORT` | `qdrant_port` | `6333` | No | Port for external Qdrant instance |
| `QDRANT_COLLECTION_NAME` | `qdrant_collection_name` | `trackflow_knowledge` | No | Canonical Qdrant collection name |

---

## 4. Qdrant Collection Schema (`trackflow_knowledge`)

- **Collection Name**: `trackflow_knowledge`
- **Vectors Configuration**:
  ```json
  {
    "size": 384,
    "distance": "Cosine"
  }
  ```
- **Payload Schema**:
  ```json
  {
    "company": "trackflow",
    "source_document": "sla-delivery",
    "section": "Delivery SLA Commitments & Exceptions",
    "language": "en",
    "chunk_index": 0,
    "text": "TrackFlow manages last-mile delivery in the United States..."
  }
  ```
- **Payload Indexes**:
  - Keyword index on `company`
  - Keyword index on `source_document`
  - Keyword index on `language`

---

## 5. TypeScript DTO Mapping (`@repo/shared-types`)

```typescript
export interface KnowledgeSourceCitationDTO {
  sourceDocument: string;
  section: string;
  similarityScore: number;
}

export interface KnowledgeQueryRequestDTO {
  query: string;
  language?: string;
  topK?: number;
  minScore?: number;
}

export interface KnowledgeQueryResponseDTO {
  query: string;
  answer: string;
  isRefusal: boolean;
  sources: KnowledgeSourceCitationDTO[];
  executionTimeMs: number;
}

export interface KnowledgeHealthResponseDTO {
  status: "healthy" | "degraded" | "unhealthy";
  collectionName: string;
  indexedPointsCount: number;
  vectorDimensions: number;
}
```

---

## 6. Python Pydantic Schemas (`presentation/schemas/knowledge.py`)

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class KnowledgeSourceCitationSchema(BaseModel):
    source_document: str = Field(..., description="Canonical source document slug")
    section: str = Field(..., description="Source section title")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")

class KnowledgeQueryRequestSchema(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000, description="Natural language inquiry")
    language: Optional[str] = Field(default="en", description="Target response language")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of chunks to retrieve")
    min_score: Optional[float] = Field(default=0.62, ge=0.0, le=1.0, description="Minimum similarity threshold")

class KnowledgeQueryResponseSchema(BaseModel):
    query: str = Field(..., description="Echoed input query")
    answer: str = Field(..., description="Grounded synthesized response")
    is_refusal: bool = Field(..., description="Whether the inquiry was refused due to insufficient documentation")
    sources: List[KnowledgeSourceCitationSchema] = Field(default_factory=list, description="Citations used for answer")
    execution_time_ms: float = Field(..., description="Processing time in milliseconds")

class KnowledgeHealthResponseSchema(BaseModel):
    status: str = Field(..., description="Operational status: healthy, degraded, unhealthy")
    collection_name: str = Field(..., description="Active Qdrant collection name")
    indexed_points_count: int = Field(..., description="Total vectors indexed")
    vector_dimensions: int = Field(..., description="Vector dimensionality")
```
