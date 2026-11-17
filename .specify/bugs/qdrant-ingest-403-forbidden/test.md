# Bug Verification: Qdrant Cloud 403 Forbidden During Knowledge Base Ingestion

- **Slug**: qdrant-ingest-403-forbidden
- **Tested**: 2026-11-16
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: partial

## Summary

All unit, integration, and local/in-memory ingestion checks pass, confirming that `KnowledgeRuntimeConfig` loads and redacts `QDRANT_API_KEY`, `QdrantVectorStoreAdapter` forwards `api_key` to `QdrantClient` and respects constructor target precedence (`location`, `url`, `host`, `path`), and `scripts/ingest_knowledge_base.py` loads `services/api/.env` before resolving the Qdrant target. Result is marked `partial` because live network reproduction against the external Qdrant Cloud cluster (`QDRANT_URL`) was skipped per network-dependent check guardrails.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix, live Qdrant Cloud) | `cd services/api; uv run python ../../scripts/ingest_knowledge_base.py` (against remote `QDRANT_URL`) | skipped | Skipped per guardrail (network-dependent write/collection operation against external Qdrant Cloud cluster); verified via mocked `QdrantClient` integration tests and `--in-memory` CLI run. |
| Reproduction (post-fix, CLI in-memory & config resolution) | `cd services/api; uv run python ../../scripts/ingest_knowledge_base.py --in-memory` | pass | Parses 4 markdown docs and indexes 12 points into `trackflow_knowledge` with `location=":memory:"` taking precedence over `.env` `QDRANT_URL`. |
| New / updated tests | `cd services/api; uv run pytest tests/unit/test_knowledge_config.py tests/integration/test_qdrant_adapter.py -v` | pass | 16 passed in 44.45s (`QDRANT_API_KEY` loading, placeholder filtering, secret masking, `api_key` forwarding to `QdrantClient`, `path`/`location` precedence, and 403 hint formatting). |
| Regression suite | `cd services/api; uv run pytest tests/integration/test_knowledge_routes.py -k "test_us5_env_configuration_and_zero_credential_exposure" -v` | pass | 1 passed in 3.14s (also verified full 41-test `knowledge or qdrant` suite during fix phase). |
| Lint / type-check | `cd services/api; uv run python -m py_compile domain/knowledge/entities.py infrastructure/adapters/qdrant_vector_store_adapter.py ../../scripts/ingest_knowledge_base.py` | pass | Zero syntax or bytecode compilation errors across all modified Python modules. |

## Output Excerpts

```text
$ cd services/api; uv run python ../../scripts/ingest_knowledge_base.py --in-memory
Parsed trackflow-sla-delivery.en.md (3 chunks)
Parsed trackflow-returns-policy.en.md (3 chunks)
Parsed trackflow-carrier-coverage.en.md (3 chunks)
Parsed trackflow-storage-pricing.en.md (3 chunks)
Indexed 12 points into Qdrant collection 'trackflow_knowledge': 12 new chunks added (0 updated/skipped)
```

```text
$ cd services/api; uv run pytest tests/unit/test_knowledge_config.py tests/integration/test_qdrant_adapter.py -v
...
tests/integration/test_qdrant_adapter.py::TestQdrantVectorStoreAdapterIntegration::test_forwards_api_key_from_config_and_constructor_for_url_and_host PASSED [ 87%]
tests/integration/test_qdrant_adapter.py::TestQdrantVectorStoreAdapterIntegration::test_explicit_path_and_location_take_precedence_over_config_url PASSED [ 93%]
tests/integration/test_qdrant_adapter.py::TestQdrantVectorStoreAdapterIntegration::test_forbidden_403_error_includes_actionable_hint_and_masks_secret PASSED [100%]
======================= 16 passed, 3 warnings in 44.45s =======================
```

```text
$ cd services/api; uv run pytest tests/integration/test_knowledge_routes.py -k "test_us5_env_configuration_and_zero_credential_exposure" -v
tests/integration/test_knowledge_routes.py::TestKnowledgeRoutesIntegration::test_us5_env_configuration_and_zero_credential_exposure PASSED [100%]
================ 1 passed, 12 deselected, 3 warnings in 3.14s =================
```

## Residual Risks

- **Live Qdrant Cloud API Key Permissions**: While the code now loads `QDRANT_API_KEY` from `services/api/.env` and passes `api_key=...` to `QdrantClient`, live ingestion against the remote Qdrant Cloud endpoint (`QDRANT_URL`) depends on the configured `QDRANT_API_KEY` in `services/api/.env` being active and having write/manage permissions for the `trackflow_knowledge` collection. If the token is read-only or expired, Qdrant Cloud will still return `403 Forbidden`, though `QdrantVectorStoreAdapter` now surfaces an actionable, secret-redacted troubleshooting message.

## Recommendation

Hold for quick live-cluster check — all automated unit, integration, and in-memory CLI checks pass and prove `api_key` is forwarded and redacted properly, but because live Qdrant Cloud reproduction is network-dependent and was skipped, run `cd services/api && uv run python ../../scripts/ingest_knowledge_base.py` against your Qdrant Cloud cluster (with a write-enabled `QDRANT_API_KEY` in `services/api/.env`) to confirm end-to-end cloud ingestion before closing.
