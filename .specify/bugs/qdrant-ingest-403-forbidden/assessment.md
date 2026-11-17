# Bug Assessment: Qdrant Cloud 403 Forbidden During Knowledge Base Ingestion

- **Slug**: qdrant-ingest-403-forbidden
- **Created**: 2026-11-16
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

```text
PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo> cd services/api
>> uv run python ../../scripts/ingest_knowledge_base.py
Parsed trackflow-sla-delivery.en.md (3 chunks)
Parsed trackflow-returns-policy.en.md (3 chunks)
Parsed trackflow-carrier-coverage.en.md (3 chunks)
Parsed trackflow-storage-pricing.en.md (3 chunks)
Error during knowledge base ingestion: Unable to ensure Qdrant collection 'trackflow_knowledge': Unexpected Response: 403 (Forbidden)
Raw response content:
b'{"error":"forbidden"}'
```

## Symptom

Running `uv run python ../../scripts/ingest_knowledge_base.py` from `services/api` successfully parses and chunks all four canonical markdown documents, but fails with `KnowledgeBaseUnavailableException: Unable to ensure Qdrant collection 'trackflow_knowledge': Unexpected Response: 403 (Forbidden)` (`b'{"error":"forbidden"}'`) when calling `vector_store.ensure_collection()` against a configured Qdrant Cloud cluster (`QDRANT_URL`). Expected behavior is for the ingestion script (and FastAPI vector store adapter) to authenticate with Qdrant Cloud using `QDRANT_API_KEY` from `services/api/.env` (and/or gracefully handle constructor/environment target resolution) so that collection creation and chunk upserts succeed.

## Reproduction

1. Configure `services/api/.env` with a Qdrant Cloud cluster URL in `QDRANT_URL` (e.g., `https://<cluster-id>.europe-west6-0.gcp.cloud.qdrant.io`) and a corresponding `QDRANT_API_KEY`.
2. Change directory to `services/api`:
   ```powershell
   cd services/api
   ```
3. Run the ingestion CLI script:
   ```powershell
   uv run python ../../scripts/ingest_knowledge_base.py
   ```
4. Observe that after parsing the 4 markdown files, `vector_store.ensure_collection()` raises `Unexpected Response: 403 (Forbidden)` with body `b'{"error":"forbidden"}'`.

## Suspected Code Paths

- `services/api/infrastructure/adapters/qdrant_vector_store_adapter.py:39-97` — `QdrantVectorStoreAdapter.__init__()` accepts `url`, `host`, `port`, `path`, `location`, and `config`, but does not accept `api_key` or pass `api_key=...` to `QdrantClient(url=resolved_url, ...)` or `QdrantClient(host=resolved_host, ...)`. Additionally, `resolved_url` and `resolved_host` from `self.config` take precedence over an explicitly passed `path=...` argument when `url`/`host` are not explicitly passed.
- `services/api/domain/knowledge/entities.py:126-286` — `KnowledgeRuntimeConfig` does not define or load `qdrant_api_key` from `QDRANT_API_KEY` in `from_env()`, nor does it mask `qdrant_api_key` in `__repr__()`, `__str__()`, `to_sanitized_dict()`, or `sanitize_text()`.
- `scripts/ingest_knowledge_base.py:111-120` — `main()` checks `os.getenv("QDRANT_URL") or os.getenv("QDRANT_HOST") or os.getenv("QDRANT_PATH")` before `services/api/.env` has been loaded into `os.environ`. It therefore falls into the `else` branch (`QdrantVectorStoreAdapter(path=str(default_storage))`), where `QdrantVectorStoreAdapter.__init__()` subsequently loads `services/api/.env` via `KnowledgeRuntimeConfig.from_env()` and overrides `path` with `self.config.qdrant_url` without an API key.
- `services/api/.env.example:20-28` — Documents `QDRANT_URL`, `QDRANT_HOST`, `QDRANT_PORT`, and `QDRANT_COLLECTION_NAME`, but omits `QDRANT_API_KEY=`.
- `services/api/presentation/dependencies.py:243-274` — `get_vector_store_dep()` instantiates `QdrantVectorStoreAdapter(config=config)` and calls `adapter.ensure_collection()` on startup/first request, which will fail with the same HTTP 403 error whenever `QDRANT_URL` points to an authenticated Qdrant instance.

## Root Cause Hypothesis

**Confidence: High.**
`services/api/.env` configures a remote Qdrant Cloud cluster (`QDRANT_URL=https://...gcp.cloud.qdrant.io`) that requires authentication via `QDRANT_API_KEY`. However, `KnowledgeRuntimeConfig.from_env()` (`services/api/domain/knowledge/entities.py:232-286`) ignores `QDRANT_API_KEY`, and `QdrantVectorStoreAdapter.__init__()` (`services/api/infrastructure/adapters/qdrant_vector_store_adapter.py:83-88`) instantiates `QdrantClient(url=resolved_url, timeout=int(timeout))` without passing `api_key`. Because `qdrant_client.QdrantClient` does not automatically read `QDRANT_API_KEY` from environment variables when `api_key` is omitted, requests to the Qdrant Cloud endpoint are sent unauthenticated and rejected with HTTP `403 Forbidden` (`{"error":"forbidden"}`). In addition, `scripts/ingest_knowledge_base.py:114` checks `os.getenv("QDRANT_URL")` before `.env` is loaded, causing a mismatch between CLI target selection and adapter initialization precedence.

## Proposed Remediation

**Preferred**:
1. **Add `qdrant_api_key` to `KnowledgeRuntimeConfig` (`services/api/domain/knowledge/entities.py`)**:
   - Add `qdrant_api_key: Optional[str] = field(default=None, repr=False)` to `KnowledgeRuntimeConfig`.
   - Load `QDRANT_API_KEY` in `KnowledgeRuntimeConfig.from_env()` (treating empty or placeholder values as `None`).
   - Mask `qdrant_api_key` alongside `llm_api_key` in `__repr__()`, `__str__()`, `to_sanitized_dict()`, and `sanitize_text()` so Qdrant credentials are never leaked in logs or responses.
2. **Pass `api_key` to `QdrantClient` and fix parameter precedence in `QdrantVectorStoreAdapter` (`services/api/infrastructure/adapters/qdrant_vector_store_adapter.py`)**:
   - Add `api_key: Optional[str] = None` to `QdrantVectorStoreAdapter.__init__()`, resolving `resolved_api_key = api_key if api_key is not None else self.config.qdrant_api_key`.
   - Pass `api_key=resolved_api_key` to `QdrantClient(url=resolved_url, api_key=resolved_api_key, timeout=int(timeout))` and `QdrantClient(host=resolved_host, port=resolved_port, api_key=resolved_api_key, timeout=int(timeout))`.
   - Respect explicit constructor overrides (`location`, `path`, `url`, `host`) before falling back to `self.config.qdrant_url` / `self.config.qdrant_host`.
3. **Load `KnowledgeRuntimeConfig.from_env()` in `scripts/ingest_knowledge_base.py` and document `QDRANT_API_KEY` in `services/api/.env.example`**:
   - In `scripts/ingest_knowledge_base.py`, load `config = KnowledgeRuntimeConfig.from_env()` before checking whether remote Qdrant settings (`config.qdrant_url`, `config.qdrant_host`, or `QDRANT_PATH`) are configured, and pass `config=config` to `QdrantVectorStoreAdapter`.
   - Add `QDRANT_API_KEY=` to `services/api/.env.example` and `specs/026-rag-knowledge-base/quickstart.md`.

**Alternatives** (optional):
- Rely on an external shell export of `QDRANT_API_KEY` and patch only `QdrantVectorStoreAdapter` with `os.getenv("QDRANT_API_KEY")` — rejected because it bypasses `KnowledgeRuntimeConfig` secret masking and breaks consistency with User Story 5's centralized configuration pattern.

**Files likely to change**:
- `services/api/domain/knowledge/entities.py`
- `services/api/infrastructure/adapters/qdrant_vector_store_adapter.py`
- `scripts/ingest_knowledge_base.py`
- `services/api/.env.example`
- `specs/026-rag-knowledge-base/quickstart.md`
- `services/api/tests/unit/test_knowledge_config.py`
- `services/api/tests/integration/test_qdrant_adapter.py`
- `services/api/tests/integration/test_knowledge_routes.py`

**Tests to add or update**:
- Unit tests in `services/api/tests/unit/test_knowledge_config.py` verifying `QDRANT_API_KEY` loading, placeholder handling, and secret masking in `repr()`, `str()`, `to_sanitized_dict()`, and `sanitize_text()`.
- Unit/integration tests in `services/api/tests/integration/test_qdrant_adapter.py` verifying that `QdrantVectorStoreAdapter` forwards `api_key` from `KnowledgeRuntimeConfig` (or constructor) to `QdrantClient` when `url` or `host` is used, and respects explicit `path`/`location` overrides even when `QDRANT_URL` is set in `.env`.
- Integration test updates in `services/api/tests/integration/test_knowledge_routes.py` confirming `QDRANT_API_KEY` is documented in `services/api/.env.example` and that route tests isolate or handle Qdrant configuration deterministically.

## Risks & Considerations

- **Credential Safety**: `QDRANT_API_KEY` is a sensitive bearer/JWT credential and must receive the exact same redaction guarantees in `KnowledgeRuntimeConfig` as `LLM_API_KEY`.
- **Remote Cluster Token Permissions**: If a user's `QDRANT_API_KEY` in `services/api/.env` has expired, been revoked, or is scoped as read-only (`"access": "r"` or restricted collection access) on Qdrant Cloud, Qdrant Cloud may still return `403 Forbidden` on `create_collection` / `upsert` even after the `api-key` header is sent. Improving the error message in `QdrantVectorStoreAdapter` when a 401/403 response occurs (hinting to check `QDRANT_API_KEY` permissions or unset `QDRANT_URL` for local storage) will make troubleshooting clear.
- **Test Isolation**: When `services/api/.env` contains a live `QDRANT_URL`, integration tests (`test_knowledge_routes.py`) that call `KnowledgeRuntimeConfig.from_env()` without overriding `QDRANT_URL` will hit the remote Qdrant Cloud cluster instead of `:memory:` unless isolated or configured with valid credentials.

## Open Questions

- None.
