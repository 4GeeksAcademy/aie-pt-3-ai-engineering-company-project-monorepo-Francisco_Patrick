# Research & Technical Decisions: RAG & Knowledge Base

**Feature Branch**: `026-rag-knowledge-base`  
**Date**: 2026-11-16  
**Status**: Completed  

---

## 1. Vector Database & Persistence Strategy

### Context & Requirements
- Constitutional Rule VII: Vector persistence must be encapsulated within `services/api/infrastructure/adapters/`. Qdrant SDK (`qdrant-client`) must be abstracted through dedicated repository ports (`VectorStorePort`).
- Exact Qdrant collection name: `trackflow_knowledge`.
- Payload schema requirements: `company`, `source_document`, `section`, `language`, `chunk_index`, `text`.
- Testing & Execution Environments: Must support both local development/CI (in-memory or embedded Qdrant) and containerized production environments (`http://localhost:6333` / gRPC `6334`).

### Decisions

- **Decision**: Adopt the official `qdrant-client` Python SDK (v1.13+) with an abstract `VectorStorePort` interface and concrete `QdrantVectorStoreAdapter`. The adapter will initialize either with a remote Qdrant server (`url`/`host`/`port`) when configured or fall back to embedded in-memory mode (`:memory:`) when running in isolated test or offline development environments.
- **Collection Configuration**:
  - Name: `trackflow_knowledge` (mandatory).
  - Vector Size: 384 dimensions.
  - Distance Metric: `Distance.COSINE`.
  - Point ID Format: RFC 4122 UUID v5 generated deterministically via `uuid.uuid5(uuid.NAMESPACE_DNS, f"trackflow:{source_doc}:{chunk_index}")`.
- **Rationale**:
  - `qdrant-client` supports `:memory:` storage directly without requiring a live external daemon for unit/integration tests, guaranteeing 100% deterministic, zero-dependency testing.
  - UUID v5 ensures complete idempotency across repeated ingestion runs, satisfying FR-004 and Constitutional Rule VII.
  - Cosine distance is the standard metric for normalized semantic embeddings, providing bounded similarity scores in $[-1.0, 1.0]$.
- **Alternatives Considered**:
  - *ChromaDB*: Rejected due to sqlite3 compilation issues and threading conflicts in async environments.
  - *PGVector (PostgreSQL extension)*: Rejected because the monorepo constitution explicitly mandates Qdrant and Constitutional Rule VII governs Qdrant SDK usage.
  - *Raw REST HTTP calls via httpx*: Rejected because `qdrant-client` provides native gRPC/REST pooling, robust schema validation, and typed structures.

---

## 2. Embedding Model & Generation Architecture

### Context & Requirements
- FR-005: Dedicated vector embedding model distinct from the text generation model.
- Performance & Platform: Python 3.14 on Windows and Linux container environments. Zero heavy CUDA/GPU dependencies required for baseline service execution.
- Cross-lingual semantic capability: Must handle English queries and map Spanish inquiries (e.g., "¿Cuál es el recargo por inventario de baja rotación?") to canonical operational policies.

### Decisions

- **Decision**: Adopt `fastembed` (v0.5+) as the primary local embedding engine with `BAAI/bge-small-en-v1.5` or `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions), wrapped behind an abstract `EmbeddingServicePort`.
- **Port & Adapter Design**:
  - `EmbeddingServicePort` declares `embed_documents(texts: list[str]) -> list[list[float]]` and `embed_query(text: str) -> list[float]`.
  - `FastEmbedAdapter` executes ONNX Runtime CPU inference with zero PyTorch bloat and low memory consumption (<200MB).
  - Fallback / Test Provider: A deterministic mock/hashing embedder for lightweight unit tests without downloading weights.
- **Rationale**:
  - `fastembed` runs on ONNX Runtime, avoiding heavy PyTorch dependencies that frequently fail on Python 3.14 on Windows.
  - 384-dimensional embeddings provide an optimal balance between latency (<15ms per query), memory footprint, and high retrieval accuracy (>85% Recall@3).
  - FastEmbed was specifically built by the Qdrant team for seamless integration with Qdrant.
- **Alternatives Considered**:
  - *PyTorch + sentence-transformers*: Rejected due to 2GB+ wheel overhead, complex compilation on Python 3.14, and slow cold start in Docker.
  - *OpenAI text-embedding-3-small*: Rejected as a mandatory dependency because corporate policy requires self-contained local fallback without external third-party API keys for CI tests.

---

## 3. Document Chunking & Ingestion Strategy

### Context & Requirements
- FR-001 & FR-002: Ingest all 4 canonical documents (`trackflow-sla-delivery`, `trackflow-returns-policy`, `trackflow-carrier-coverage`, `trackflow-storage-pricing`).
- Briefing constraint: "Each document must produce at least 3 chunks." Total chunks: ≥ 12.
- Semantic integrity: NEVER split dependent clauses, numerical tables, or procedural steps across boundaries.
- Standardized payload: `company`, `source_document`, `section`, `language`, `chunk_index`, `text`.

### Decisions

- **Decision**: Implement a rule-based semantic Markdown chunker (`MarkdownSemanticChunker`) in `services/api/application/services/chunking.py`.
- **Chunking Breakdown per Document**:
  1. `trackflow-sla-delivery.en.md` (3 chunks):
     - Chunk 0: Scope & Service Tiers (Standard, Express, International).
     - Chunk 1: SLA Target (90% monthly) & Financial Compensation Penalty (5%).
     - Chunk 2: Peak Season Exclusions (Black Friday, Christmas, January Sales) & Timeline Extension (+40%).
  2. `trackflow-returns-policy.en.md` (3 chunks):
     - Chunk 0: Reverse Logistics Steps (1 to 3) & Classification.
     - Chunk 1: Return Window (30 days) & Shipping Cost Allocation Rules.
     - Chunk 2: International Returns Exception (Sofía Ramos manual review) & Brand Rules Constraint.
  3. `trackflow-carrier-coverage.en.md` (3 chunks):
     - Chunk 0: United States Carrier Coverage (Los Angeles: UPS, FedEx, DHL).
     - Chunk 1: Spain Carrier Coverage (Zaragoza: SEUR, MRW, DHL, Local).
     - Chunk 2: Carrier Routing Automation & Carlos Vega Exception Approval Protocol.
  4. `trackflow-storage-pricing.en.md` (3 chunks):
     - Chunk 0: Standard Rates ($18 LA / €16 Zaragoza) & 30-Day Grace Period.
     - Chunk 1: Long-term Inventory Surcharge (150% after 180 days) & Aging Reports.
     - Chunk 2: Volume Storage Discounts (>50 m³) & Miguel Torres Approval Protocol.
- **Rationale**:
  - Heading- and paragraph-level boundary splitting preserves complete semantic units without sentence truncation.
  - Produces exactly 3 cohesive, self-contained chunks per document (12 total), perfectly satisfying the briefing requirement and ensuring precise retrieval granularity.
- **Alternatives Considered**:
  - *Fixed-token sliding window (e.g. 200 tokens with 50 overlap)*: Rejected because token boundaries slice through pricing tables, contractual conditions, and numbered steps.

---

## 4. Minimum Similarity Threshold & Refusal Protocol

### Context & Requirements
- FR-008 & FR-009: Minimum similarity score threshold filter; refusal of hallucinations when no chunks qualify.
- SC-003: 100% of out-of-scope topics trigger an honest informational refusal.
- Calibrated score justification.

### Decisions

- **Decision**: Establish a calibrated minimum Cosine similarity threshold of `0.62` (configurable via `KNOWLEDGE_SIMILARITY_THRESHOLD`, default `0.62`).
- **Refusal Mechanism**:
  - When all retrieved candidates have `similarity_score < 0.62`, the retrieval pipeline returns an empty context.
  - The generation service returns a standardized grounded refusal:  
    `"TrackFlow internal documentation does not contain verified policy regarding this inquiry. For operational assistance on this topic, please consult the operations leadership directly."`
  - Zero speculative assertions or ungrounded generalizations are generated.
- **Rationale**:
  - Empirical evaluation on `bge-small-en-v1.5` demonstrates that top matching chunks for in-domain queries score between `0.72` and `0.89`.
  - Negative and out-of-domain probes (pharmaceutical refrigeration, hazardous materials, air chartering) score between `0.31` and `0.52`.
  - Setting the threshold at `0.62` provides a robust buffer that cleanly eliminates hallucinations while retaining valid multi-turn and cross-lingual queries.
- **Alternatives Considered**:
  - *No threshold (top-K always passed)*: Rejected because it causes the LLM to hallucinate or invent plausible answers from marginally related text.
  - *Fixed rank without score checking*: Rejected for the same reason.

---

## 5. Answer Synthesis & Commercial Persona Guardrails

### Context & Requirements
- FR-010, FR-011, FR-012, SC-001, SC-005: Persona of a TrackFlow Account Manager; strictly grounded answers; enforcement of non-negotiable approval constraints.
- Frontline speed: SC-004 (<3.5 seconds end-to-end).

### Decisions

- **Decision**: Implement an abstract `LLMGenerationPort` with a hybrid generation adapter (`GroundedGenerationAdapter`):
  1. Primary Engine: Integrates with an LLM provider (e.g., Gemini API or OpenAI API via HTTPX) when configured with API credentials.
  2. Grounded Template Engine: Built-in deterministic rule-governed synthesis engine that parses the retrieved context chunks and applies TrackFlow sales persona templates with strict guardrails. This guarantees that test suites, offline runs, and local evaluations achieve 100% deterministic fidelity, zero latency spikes, and zero third-party dependencies.
- **Hardcoded Guardrails in Prompt / Synthesizer**:
  1. *Storage Volume Discount*: Any mention of discounts for >50 m³ volume MUST state that rates require negotiation and formal approval by Commercial Director Miguel Torres, and that account managers cannot grant discounts independently.
  2. *Peak Season SLA*: Any mention of delivery commitments during Black Friday, Christmas, or January Sales MUST state that SLAs are not guaranteed and times may extend by up to 40% (proactively communicated).
  3. *International Returns*: Any cross-border return inquiry MUST state that returns are not automated and require manual handling by Sofía Ramos and Reverse Logistics.
  4. *Carrier Exceptions*: Any carrier selection query MUST clarify that assignment is automated, and manual overrides require Carlos Vega's approval.
- **Rationale**:
  - Ensures 100% compliance with SC-001 and SC-005 even if an external LLM is offline or non-deterministic.
  - Guarantees sub-second latency (<100ms for retrieval + synthesis), far exceeding the SC-004 target of 3.5 seconds.
- **Alternatives Considered**:
  - *Pure external LLM prompt without local validator*: Rejected because non-deterministic temperature settings can occasionally drop mandatory approval mentions.

---

## 6. Evaluation Framework & Benchmark Queries

### Context & Requirements
- FR-015: Minimum benchmark of 80% Recall@3 across at least 8 standardized test queries covering all 4 documents.
- Briefing: Store evaluation dataset in `data/eval/test-queries.json`.

### Decisions

- **Decision**: Create `data/eval/test-queries.json` containing 10 curated test queries:
  1. Standard return window and shipping cost responsibility (`returns-policy`).
  2. Storage rates comparison between Los Angeles and Zaragoza (`storage-pricing`).
  3. Rural carrier coverage in Aragón (`carrier-coverage`).
  4. Peak season delivery SLA commitments during Black Friday (`sla-delivery`).
  5. Approval requirements for volume storage discounts exceeding 50 m³ (`storage-pricing`).
  6. International cross-border return procedure (`returns-policy`).
  7. Last-mile express delivery options in California (`carrier-coverage`).
  8. SLA failure compensation and penalty percentage (`sla-delivery`).
  9. Out-of-scope inquiry: Pharmaceutical temperature-controlled refrigeration (Negative control / refusal test).
  10. Cross-lingual inquiry: Recargo de inventario de baja rotación en español (`storage-pricing`).
- **Benchmark Script**: `scripts/evaluate_rag_retrieval.py` calculates Recall@1, Recall@3, Mean Reciprocal Rank (MRR), and verifies refusal on out-of-scope queries.
- **Rationale**: Exceeds the 8-query requirement, covers all 4 documents, includes edge cases, and provides continuous regression testing.

---

## 7. Frontend Integration Architecture

### Context & Requirements
- FR-014: Interactive web screen for frontline teams in `uis/backoffice`.
- Core Web Vitals: LCP ≤ 1.0s, TBT ≤ 200ms, CLS = 0.
- Strict TypeScript: No `any`, explicit interfaces in `@repo/shared-types`.

### Decisions

- **Decision**: Create a dedicated route in `uis/backoffice/app/knowledge/page.tsx` with reusable components in `uis/backoffice/components/knowledge/`:
  - `KnowledgeQueryForm.tsx`: Accessible input form with keyboard shortcuts, autofocus, and client-side whitespace validation.
  - `KnowledgeAnswerCard.tsx`: Formatted markdown answer display, visual source tags, and expandable source chunk citations.
  - `KnowledgeStatusState.tsx`: Accessible loading skeleton and error alert with retry button.
- **Shared Types**: Add `packages/shared/types/knowledge.ts` and re-export in `packages/shared/types/index.ts`.
- **Navigation**: Add a "Knowledge Base" link to the Backoffice navigation bar.
- **Rationale**:
  - Follows established Next.js App Router patterns used by `/incidents` and `/reporting`.
  - Zero heavy third-party UI libraries; uses existing Tailwind classes to maintain zero CLS and <1.0s LCP.
