# Bug Assessment: SQLModel Database Port Defaults to 5432 Despite .env Definition

- **Slug**: sqlmodel-db-port-fallback
- **Created**: 2026-10-15
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The user reported:
> In `services/api/infrastructure/persistence/sqlmodel/client.py`, the `db_port = os.getenv("port") or os.getenv("DB_PORT", "5432")` falls to the default port. This shall not happen due the .env HAS defined the port.

During testing, the user inserted a debugging print statement `print(db_port)` at line 37 in `services/api/infrastructure/persistence/sqlmodel/client.py` and observed `5432` in the terminal and Docker backend logs, even though `services/api/.env` explicitly defined `port=6543`.

## Symptom

When running the backend service (via Docker Compose or from root), `SQLModelClientManager.build_database_url()` resolves `db_port` to `"5432"` (the default PostgreSQL port) instead of the port configured in `services/api/.env` (`port=6543`). As a result, the database client attempts to connect to `5432`, fails to authenticate or reach the Supabase connection pooler on port 6543, and falls back to local SQLite persistence (`inventory.db`).

Expected behavior: If `port` or `DB_PORT` is specified in `services/api/.env` (e.g. `port=6543`), `db_port` should resolve to `"6543"`, allowing the application to connect to the configured host and port without falling back to `5432` or SQLite.

## Reproduction

1. Check `services/api/.env`: it defines `host=aws-1-eu-west-1.pooler.supabase.com` and `port=6543`.
2. Check monorepo root `.env`: it defines `host=db.iwminubqjxjegznnrccj.supabase.co` and `port=5432`.
3. Start the application stack via `docker compose up -d --build ui` or `docker compose up backend`.
4. Inspect the backend container logs (`docker logs trackflow-backend`).
5. Observe that `db_port` prints `5432` and `client.py` issues:
   ```text
   5432
   [WARNING] Database connection failed (host: db.iwminubqjxjegznnrccj.supabase.co, port: 5432): (psycopg2.OperationalError) ... port 5432 failed: Network is unreachable ... Falling back to SQLite: sqlite:////app/services/api/inventory.db
   ```
6. Alternatively, run python from the monorepo root: `load_dotenv()` in `client.py` loads the root `.env` (`port=5432`) rather than `services/api/.env` (`port=6543`).

## Suspected Code Paths

- [services/api/infrastructure/persistence/sqlmodel/client.py:14](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/persistence/sqlmodel/client.py#L14) — Calls `load_dotenv()` with no explicit path and default `override=False`. When running inside Docker (where `WORKDIR` is `/app/services`), `load_dotenv()` looks for `/app/services/.env` (which does not exist; the file is located at `/app/services/api/.env`).
- [services/api/infrastructure/persistence/sqlmodel/client.py:33-38](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/persistence/sqlmodel/client.py#L33-L38) — `build_database_url()` accesses `os.getenv("port") or os.getenv("DB_PORT", "5432")`. Because `services/api/.env` is never loaded into `os.environ` inside the container or when run outside its directory, `os.getenv("port")` either reads the container environment injected from root `.env` (`5432`) or falls back to the default `"5432"`.
- [docker-compose.yml:45-46](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml#L45-L46) — The `backend` service specifies `env_file: - .env` (root monorepo `.env` where `port=5432`), while `services/api/.env` (where `port=6543`) is neither referenced in `docker-compose.yml` nor loaded with override in `client.py`.
- [.env:20-26](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/.env#L20-L26) — Root `.env` contains conflicting database configurations (`host=db.iwminubqjxjegznnrccj.supabase.co`, `port=5432`) that diverge from `services/api/.env` (`host=aws-1-eu-west-1.pooler.supabase.com`, `port=6543`).

## Root Cause Hypothesis

**Confidence: High**

The symptom is caused by a dual-origin environment configuration and dotenv loading flaw:

1. **Unanchored Dotenv Loading**: In [services/api/infrastructure/persistence/sqlmodel/client.py:14](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/persistence/sqlmodel/client.py#L14), `load_dotenv()` is called without specifying the absolute path to `services/api/.env`. Python-dotenv defaults to `os.getcwd()` (which is `/app/services` inside Docker or monorepo root in standard multi-directory terminal sessions). Consequently, `services/api/.env` is never loaded.
2. **Environment Variable Precedence & Stale Root `.env` in Docker**: In [docker-compose.yml:45-46](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml#L45-L46), `backend` imports the root `.env` file, which explicitly hardcodes `port=5432` and `host=db.iwminubqjxjegznnrccj.supabase.co`. Because Docker injects these variables directly into the container process's `os.environ`, any subsequent `load_dotenv()` call without `override=True` is ignored.
3. As a result, `os.getenv("port")` evaluates to `"5432"` (inherited from Docker Compose / root `.env`) instead of the intended `"6543"` declared in `services/api/.env`.

## Proposed Remediation

**Preferred**:
1. In [services/api/infrastructure/persistence/sqlmodel/client.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/persistence/sqlmodel/client.py), anchor the dotenv loading to the canonical `services/api/.env` file path using `os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))`. Pass `override=True` so that explicit service-level `.env` settings take precedence over inherited shell/Docker defaults if present, while gracefully falling back to standard environment variables.
2. In [docker-compose.yml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml), update the `backend` service `env_file` list or synchronize root `.env` and `services/api/.env` so that Docker Compose mounts the consistent database host (`aws-1-eu-west-1.pooler.supabase.com`) and port (`6543`), or allows `services/api/.env` to override root `.env`.
3. In [services/api/infrastructure/persistence/sqlmodel/client.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/persistence/sqlmodel/client.py), remove temporary debug `print(db_port)` left on line 37.

**Alternatives**:
- *Docker-only alignment*: Only update root `.env` to match `services/api/.env`. While this fixes Docker Compose, it leaves standalone execution or test execution fragile if executed from outside `services/api`.
- *Code-only override*: Only load `services/api/.env` with `override=True` in `client.py`. This guarantees Python always picks up `services/api/.env` regardless of working directory or Docker root `.env` injections.

**Files likely to change**:
- `services/api/infrastructure/persistence/sqlmodel/client.py`
- `docker-compose.yml` (and/or `.env` in root)
- `services/api/tests/unit/test_sqlmodel_client.py`

**Tests to add or update**:
- Unit test in `tests/unit/test_sqlmodel_client.py` ensuring that `build_database_url()` respects custom `port` / `DB_PORT` set via `monkeypatch` or custom `.env` path and correctly includes the custom port in the PostgreSQL connection string.

## Risks & Considerations

- **Secret & Connection Divergence**: If `services/api/.env` points to the Supabase transaction pooler (`aws-1-eu-west-1.pooler.supabase.com:6543`) with `user=postgres.iwminubqjxjegznnrccj`, credentials must be valid for password authentication over SSL; if authentication fails, the resilient SQLite fallback in `client.py` will catch it and prevent crash loops.
- **Docker Cache**: After updating `docker-compose.yml` or `.env`, containers should be recreated (`docker compose up -d backend`) for updated environment variables to take effect.

## Open Questions

- Should `services/api/.env` always take precedence over the root monorepo `.env`, or should the root `.env` database variables be updated to match the pooler configuration (`aws-1-eu-west-1.pooler.supabase.com:6543`) across the entire stack?
