# Bug Fix: SQLModel Database Port Defaults to 5432 Despite .env Definition

- **Slug**: sqlmodel-db-port-fallback
- **Fixed**: 2026-10-15
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Anchored dotenv loading in SQLModel client to the service-specific `services/api/.env` with `override=True`, aligned environment variable definitions across root `.env`, `services/api/.env`, and `docker-compose.yml`, removed stray debug print statements, and added regression unit tests for port resolution.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/infrastructure/persistence/sqlmodel/client.py` | modified | Anchors `load_dotenv` to `services/api/.env` with `override=True`; removes debug `print(db_port)`. |
| `docker-compose.yml` | modified | Adds `services/api/.env` to backend `env_file` list and adds `/app/services/api` to `PYTHONPATH`. |
| `.env` | modified | Synchronizes database host (`aws-1-eu-west-1.pooler.supabase.com`), port (`6543`), user, and `DATABASE_URL` with Supabase pooler settings. |
| `services/api/.env` | modified | Updates `DATABASE_URL` connection string to match configured host `aws-1-eu-west-1.pooler.supabase.com` and port `6543`. |
| `services/api/tests/unit/test_sqlmodel_client.py` | modified | Adds tests covering explicit `port`, `DB_PORT` fallback, and default `5432` fallback behavior. |

## Diff Highlights (optional)

```python
# services/api/infrastructure/persistence/sqlmodel/client.py
_api_env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
)
if os.path.exists(_api_env_path):
    load_dotenv(dotenv_path=_api_env_path, override=True)
else:
    load_dotenv()
```

```yaml
# docker-compose.yml
    environment:
      - PYTHONPATH=/app:/app/services:/app/services/api
    env_file:
      - .env
      - services/api/.env
```

## Tests Added or Updated

- `services/api/tests/unit/test_sqlmodel_client.py::test_sqlmodel_manager_custom_port` — Verifies that `build_database_url()` respects `port="6543"` in the connection string without defaulting to 5432.
- `services/api/tests/unit/test_sqlmodel_client.py::test_sqlmodel_manager_db_port_fallback` — Verifies fallback to `DB_PORT` when `port` is unset.
- `services/api/tests/unit/test_sqlmodel_client.py::test_sqlmodel_manager_default_port_fallback` — Verifies fallback to `"5432"` only when neither `port` nor `DB_PORT` is specified.

## Local Verification

- Commands run:
  - `.venv\Scripts\pytest tests/unit/test_sqlmodel_client.py` → 7 passed in 9.51s
  - `.venv\Scripts\pytest tests/unit/` → 77 passed in 123.54s
  - `docker compose up -d backend` → Container recreated and started
  - `docker compose exec backend python -c "from infrastructure.persistence.sqlmodel.client import SQLModelClientManager; print(SQLModelClientManager().build_database_url())"` → Database URL resolves with port `6543` and host `aws-1-eu-west-1.pooler.supabase.com` without printing `5432`.
- Manual checks:
  - Verified Docker backend container logs via `docker compose logs backend`: host and port correctly reflected as `aws-1-eu-west-1.pooler.supabase.com:6543`.

## Deviations from Assessment

None. The fix strictly implemented the preferred remediation proposed in the assessment.

## Follow-ups

- Verify password credentials in Supabase project if live pooling over IPv4 pooler `aws-1-eu-west-1.pooler.supabase.com:6543` is required instead of local SQLite fallback.
