# Bug Fix: Qdrant Cloud 403 Forbidden During Knowledge Base Ingestion

- **Slug**: qdrant-ingest-403-forbidden
- **Fixed**: 2026-11-16
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Added `QDRANT_API_KEY` loading and secret redaction to `KnowledgeRuntimeConfig`, forwarded `api_key` to `QdrantClient` while enforcing explicit constructor target precedence (`location`, `url`, `host`, `path`) in `QdrantVectorStoreAdapter`, and updated `scripts/ingest_knowledge_base.py` to load `services/api/.env` via `KnowledgeRuntimeConfig.from_env()` before resolving the Qdrant target. Also improved 401/403 error messages with sanitized troubleshooting guidance and isolated `test_knowledge_routes.py` from live `QDRANT_URL` settings in `services/api/.env`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/domain/knowledge/entities.py` | modified | Added `qdrant_api_key` and `has_qdrant_api_key` to `KnowledgeRuntimeConfig`, loaded `QDRANT_API_KEY` in `from_env()` with placeholder filtering, and redacted `qdrant_api_key` in `__repr__()`, `__str__()`, `to_sanitized_dict()`, and `sanitize_text()`. |
| `services/api/infrastructure/adapters/qdrant_vector_store_adapter.py` | modified | Added `api_key` parameter to `QdrantVectorStoreAdapter.__init__()`, passed `api_key=resolved_api_key` to `QdrantClient` for `url` and `host` targets, fixed constructor target precedence (`location`, `url`, `host`, `path` before `self.config`), and added `_format_qdrant_error()` with secret sanitization and 401/403 hints. |
| `scripts/ingest_knowledge_base.py` | modified | Loaded `config = KnowledgeRuntimeConfig.from_env()` in `main()` prior to checking Qdrant target configuration and passed `config=config` to `QdrantVectorStoreAdapter` and `FastEmbedAdapter`. |
| `services/api/.env.example` | modified | Added `QDRANT_API_KEY=` under Embedding & Vector Store Configuration. |
| `specs/026-rag-knowledge-base/quickstart.md` | modified | Documented `QDRANT_API_KEY=` in Prerequisites and Scenario 5 verification steps. |
| `services/api/tests/unit/test_knowledge_config.py` | modified | Added unit test assertions for `QDRANT_API_KEY` default values, custom env loading, placeholder handling, and secret masking across `repr()`, `str()`, `to_sanitized_dict()`, and `sanitize_text()`. |
| `services/api/tests/integration/test_qdrant_adapter.py` | added test | Added tests for `api_key` forwarding on `url`/`host`, explicit `path`/`location` precedence over `config.qdrant_url`, and 403 Forbidden error hint + secret redaction. |
| `services/api/tests/integration/test_knowledge_routes.py` | modified | Isolated route integration tests from ambient `QDRANT_URL`/`QDRANT_HOST`/`QDRANT_PATH` in `.env` and verified `QDRANT_API_KEY` presence in `.env.example` and zero credential leakage. |

## Diff Highlights (optional)

```python
# services/api/domain/knowledge/entities.py
raw_qdrant_key = source.get("QDRANT_API_KEY")
cleaned_qdrant_key: Optional[str] = None
if raw_qdrant_key and raw_qdrant_key.strip():
    candidate = raw_qdrant_key.strip()
    if candidate.lower() not in PLACEHOLDER_API_KEYS:
        cleaned_qdrant_key = candidate
```

```python
# services/api/infrastructure/adapters/qdrant_vector_store_adapter.py
if location is not None:
    self._client = QdrantClient(location=location)
elif explicit_url:
    self._client = QdrantClient(
        url=explicit_url,
        api_key=resolved_api_key,
        timeout=int(timeout),
    )
elif explicit_host:
    self._client = QdrantClient(
        host=explicit_host,
        port=resolved_port,
        api_key=resolved_api_key,
        timeout=int(timeout),
    )
elif explicit_path:
    os.makedirs(explicit_path, exist_ok=True)
    self._client = QdrantClient(path=explicit_path)
elif self.config.qdrant_url:
    self._client = QdrantClient(
        url=self.config.qdrant_url,
        api_key=resolved_api_key,
        timeout=int(timeout),
    )
```

## Tests Added or Updated

- `services/api/tests/unit/test_knowledge_config.py::TestKnowledgeRuntimeConfig::test_defaults_when_env_is_empty` — verifies `qdrant_api_key is None` and `has_qdrant_api_key is False` by default.
- `services/api/tests/unit/test_knowledge_config.py::TestKnowledgeRuntimeConfig::test_custom_environment_variables_loaded_accurately` — verifies `QDRANT_API_KEY` loads into `config.qdrant_api_key`.
- `services/api/tests/unit/test_knowledge_config.py::TestKnowledgeRuntimeConfig::test_placeholder_api_keys_treated_as_unconfigured` — verifies placeholder `QDRANT_API_KEY` values resolve to `None`.
- `services/api/tests/unit/test_knowledge_config.py::TestKnowledgeRuntimeConfig::test_secret_masking_in_repr_str_and_sanitized_dict` — verifies `QDRANT_API_KEY` is redacted in `repr()`, `str()`, and `to_sanitized_dict()`.
- `services/api/tests/unit/test_knowledge_config.py::TestKnowledgeRuntimeConfig::test_sanitize_text_redacts_secret_occurrences` — verifies `sanitize_text()` strips raw `QDRANT_API_KEY` values from error/log strings.
- `services/api/tests/integration/test_qdrant_adapter.py::TestQdrantVectorStoreAdapterIntegration::test_forwards_api_key_from_config_and_constructor_for_url_and_host` — pins down `api_key` forwarding to `QdrantClient` for both `url` and `host` configurations.
- `services/api/tests/integration/test_qdrant_adapter.py::TestQdrantVectorStoreAdapterIntegration::test_explicit_path_and_location_take_precedence_over_config_url` — pins down constructor `path` and `location` precedence when `QDRANT_URL` is set in config.
- `services/api/tests/integration/test_qdrant_adapter.py::TestQdrantVectorStoreAdapterIntegration::test_forbidden_403_error_includes_actionable_hint_and_masks_secret` — pins down actionable 403 troubleshooting guidance and secret redaction.
- `services/api/tests/integration/test_knowledge_routes.py::TestKnowledgeRoutesIntegration::test_us5_env_configuration_and_zero_credential_exposure` — verifies `QDRANT_API_KEY` in `.env.example` and zero credential leakage in API responses.

## Local Verification

- Commands run:
  - `cd services/api; uv run pytest -k "knowledge or qdrant" -v` → `41 passed in 120.99s`
  - `cd services/api; uv run python ../../scripts/ingest_knowledge_base.py --in-memory` → `Indexed 12 points into Qdrant collection 'trackflow_knowledge': 12 new chunks added (0 updated/skipped)`
- Manual checks: Verified `services/api/.env.example` and `specs/026-rag-knowledge-base/quickstart.md` include `QDRANT_API_KEY=`.

## Deviations from Assessment

None.

## Follow-ups

- When running against a live Qdrant Cloud cluster (`QDRANT_URL`), ensure the `QDRANT_API_KEY` in `services/api/.env` has write/manage permissions (`"access": "m"` or read-write access for `trackflow_knowledge`), or leave `QDRANT_URL=` empty for local `.qdrant_storage` / `:memory:` operation.
