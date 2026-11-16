# Quickstart Validation Guide: RAG & Knowledge Base

**Feature Branch**: `026-rag-knowledge-base`  
**Date**: 2026-11-16  
**Status**: Ready for Implementation  

---

## Prerequisites

1. **Python Environment**: Python 3.14+ managed via `uv` in `services/api`.
2. **Node.js Environment**: Node.js 20+ with npm workspaces for `uis/backoffice` and `packages/shared`.
3. **Environment Configuration (`services/api/.env`)**:
   - Inspect `services/api/.env.example` and ensure `services/api/.env` contains the AI, LLM, Agent, Embedding, and Qdrant configuration variables:
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
4. **Qdrant Vector Database**:
   - For local development / testing: Automatically boots in `:memory:` mode when `QDRANT_HOST` and `QDRANT_URL` are unset, requiring no external processes.
   - For containerized or live operation: Qdrant Docker container running on port 6333 (`docker run -p 6333:6333 qdrant/qdrant`).

---

## 1. Setup & Ingestion

### Step 1.1: Install Dependencies
```bash
# In backend services
cd services/api
uv sync

# In root monorepo (build shared types)
cd ../..
npm run build --workspace=@repo/shared-types
```

### Step 1.2: Ingest Knowledge Base Documents
Execute the idempotent seeding script to index all 4 documents into the `trackflow_knowledge` collection:
```bash
cd services/api
uv run python ../../scripts/ingest_knowledge_base.py
```
**Expected Outcome**:
- Output confirms parsing of:
  - `trackflow-sla-delivery.en.md` (3 chunks)
  - `trackflow-returns-policy.en.md` (3 chunks)
  - `trackflow-carrier-coverage.en.md` (3 chunks)
  - `trackflow-storage-pricing.en.md` (3 chunks)
- Total 12 points indexed into Qdrant collection `trackflow_knowledge`.
- Rerunning the command displays `0 new chunks added (12 updated/skipped)`, confirming idempotency.

---

## 2. Benchmark Retrieval Accuracy (Recall@3)

Execute the evaluation benchmark suite against the standardized 10-query dataset:
```bash
uv run python ../../scripts/evaluate_rag_retrieval.py --eval-file data/eval/test-queries.json
```
**Expected Outcome**:
- Overall Recall@3 $\ge 80\%$ (target benchmark).
- Average retrieval latency $< 50$ ms.
- Out-of-scope test query correctly flagged as below similarity threshold (`0.62`), demonstrating zero hallucination.

---

## 3. End-to-End API Validation Scenarios

Start the FastAPI application:
```bash
cd services/api
uv run uvicorn main:app --reload --port 8000
```

### Scenario 1: Standard Return Window & Shipping Cost Inquiry (P1)
```bash
curl -X POST http://localhost:8000/api/v1/knowledge/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is TrackFlow'\''s standard return window and who covers return shipping costs?",
    "top_k": 3
  }'
```
**Expected Outcome**:
- HTTP 200 OK
- `is_refusal: false`
- `answer` states standard return window is 30 days from delivery and return shipping costs are covered by the client brand (TrackFlow covers only transit damage or delivery error).
- `sources` references `returns-policy`.

---

### Scenario 2: Peak Season Delivery SLA Inquiry with Guardrail (P2)
```bash
curl -X POST http://localhost:8000/api/v1/knowledge/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Can we guarantee 90% delivery SLA during Black Friday sales?",
    "top_k": 3
  }'
```
**Expected Outcome**:
- HTTP 200 OK
- `is_refusal: false`
- `answer` explicitly states standard SLAs are **not** guaranteed during declared peak dates (Black Friday, Christmas, January Sales), notes delivery times may extend by up to 40%, and emphasizes this must be communicated in advance.
- `sources` references `sla-delivery`.

---

### Scenario 3: Volume Storage Discount Request with Miguel Torres Guardrail (P2)
```bash
curl -X POST http://localhost:8000/api/v1/knowledge/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Can we offer a discount on storage fees for a client storing 75 cubic meters?",
    "top_k": 3
  }'
```
**Expected Outcome**:
- HTTP 200 OK
- `is_refusal: false`
- `answer` states clients with >50 m³ volume can negotiate preferential rates, but explicitly warns that any discount requires approval from Commercial Director Miguel Torres, and account managers cannot grant discounts independently.
- `sources` references `storage-pricing`.

---

### Scenario 4: Out-of-Scope Query Triggering Refusal (P3)
```bash
curl -X POST http://localhost:8000/api/v1/knowledge/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is TrackFlow'\''s temperature-controlled pharmaceutical refrigeration SLA?",
    "top_k": 3
  }'
```
**Expected Outcome**:
- HTTP 200 OK
- `is_refusal: true`
- `answer` politely clarifies that TrackFlow documentation lacks information on pharmaceutical refrigeration, with guidance to contact operations leadership.
- `sources: []` (empty citations list).

---

### Scenario 5: Environment Configuration & Credential Safety Validation (P2)
1. Verify `services/api/.env.example` contains documented variables: `LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `AGENT_MODEL`, `EMBEDDING_MODEL`, `USE_FASTEMBED_ONNX`, `KNOWLEDGE_SIMILARITY_THRESHOLD`, `QDRANT_URL`, `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION_NAME`.
2. Run with default/placeholder `LLM_API_KEY=your_llm_api_key_here`:
   - Confirm queries succeed with HTTP 200 using deterministic grounded synthesis fallback.
   - Confirm `repr(config)` and `config.to_sanitized_dict()` never expose any raw `LLM_API_KEY` value.

---

## 4. Frontline Web Interface Validation (P4)

1. Start the Backoffice UI:
   ```bash
   cd uis/backoffice
   npm run dev
   ```
2. Open browser to `http://localhost:3001/knowledge`.
3. Submit a query via the search bar:
   - Verify loading spinner / skeleton appears immediately during in-flight request.
   - Verify rendered markdown response displays clearly with source document badges.
   - Test empty query submission: verify client-side validation prevents request and highlights input.
   - Simulate offline server: verify clear error banner with "Retry" action button appears.

---

## 5. Automated Verification Gates

Run all automated quality gates:
```bash
# Backend test suite
cd services/api
uv run pytest tests/unit/test_knowledge*.py tests/integration/test_knowledge*.py -v

# Monorepo TypeScript and build integrity
cd ../..
npm run typecheck
npm run build
```
**Expected Outcome**: All tests pass, 0 type errors, production build succeeds.
