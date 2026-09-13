# Phase 0 Research: Comprehensive Error Handling

**Feature**: [`spec.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/spec.md) | **Branch**: `008-error-handling`

## Research Topic 1: Frontend 3-State UI Pattern & Network Error Scoping

### Decision
Implement explicit 3-state UI management (`isLoading`, `data`, `error`) across all data-fetching components (`SuppliersPage`, `ProfilePage`, `IncidentSummaryPanel`, `IncidentListPanel`). Ensure every async request has a tightly scoped `try/catch/finally` block where the `finally` block guarantees that `isLoading` is set to `false`. Wrap low-level `fetch` calls in `lib/api.ts` within a `try/catch` block that throws a structured `ApiNetworkError` when network drops or DNS issues occur.

### Rationale
- Unhandled `fetch` rejections currently bubble up as uncaught `TypeError` exceptions.
- Components currently lack uniform error reset/retry mechanics.
- `finally` blocks guarantee loading skeletons and disabled submit states are cleared even when network exceptions occur.

### Alternatives Considered
- **Global Error Boundary Only**: Catches React component crashes but loses page context, resetting the entire view tree instead of displaying localized retry banners.
- **React Query / SWR**: Provides built-in 3-state hooks but adds extra library dependencies when standard React `useState` and `useEffect` patterns fulfill the requirements cleanly.

---

## Research Topic 2: AuthGuard Public Route Registration

### Decision
Update `PUBLIC_PATHS` in `uis/backoffice/components/AuthGuard.tsx` from `['/login', '/register']` to `['/login', '/register', '/forgot-password', '/reset-password']`.

### Rationale
- Password recovery routes (`/forgot-password` and `/reset-password`) are intended for unauthenticated users.
- Omission from `PUBLIC_PATHS` causes unauthenticated visitors to get stuck in an infinite loading spinner before being forcibly redirected to `/login`.

### Alternatives Considered
- **Disabling AuthGuard on Account Pages**: Exposes protected user pages (`/account/profile`) to unauthenticated access. Specifying exact public paths maintains security while fixing the bug.

---

## Research Topic 3: Backend FastAPI Exception Handling & Raw Error Suppression

### Decision
Refactor backend exception handling across FastAPI route handlers (`services/api/main.py`, `services/api/routes/suppliers.py`, `services/api/presentation/api/`):
1. Replace generic `except Exception as e:` returning `detail=str(e)` in `/api/incidents/analyze` with granular exception catches (`UnicodeDecodeError`, `csv.Error`, `DomainException`) and return user-safe HTTP 500 JSON payloads.
2. Wrap all TinyDB queries in `services/api/routes/suppliers.py` within `try/except` blocks returning structured HTTP 500/503 responses.
3. Map `ValueError` in user/profile creation routes to structured JSON validation error objects instead of reflecting raw Python exception text.

### Rationale
- Reflecing raw `str(e)` strings in HTTP 500 responses exposes server internal details, stack traces, and database file paths to external clients.
- Granular try/except blocks isolate specific operations (file decoding vs CSV parsing vs domain execution) instead of wrapping entire endpoints in a single monolithic handler.

### Alternatives Considered
- **Global Catch-All Middleware Only**: Catches uncaught exceptions at the top level, but loses route-specific context for structured error formatting.

---

## Research Topic 4: PII & Secret Masking in Logs & Audit Trail

### Decision
1. Sanitize console logging in `services/api/application/services/email_service.py:11` by masking email addresses (e.g. `u***@domain.com`) and omitting raw reset URL tokens.
2. Update `services/api/application/services/auth_service.py` to mask or hash email addresses before passing them to `audit_repo.log_event()`.

### Rationale
- Plaintext password reset tokens in console output could allow unauthorized password resets if logs are exposed or shared.
- Plaintext email logging in audit trails violates PII protection rules and GDPR/CCPA privacy standards.

### Alternatives Considered
- **Disabling Audit Logging for Forgot Password**: Eliminates security visibility into rate-limiting and brute-force attempts. Masking PII preserves security auditing while protecting user privacy.

---

## Research Topic 5: Python CLI Script Robustness & Exit Code Control

### Decision
1. In `scripts/analyze.py`:
   - Wrap `open(output_path, "w")` in `export_to_csv` with a `try/except IOError` block and print error details to `sys.stderr`.
   - Replace `except KeyboardInterrupt: pass` with `except KeyboardInterrupt: sys.stderr.write(...)` and `sys.exit(130)`.
2. In `scripts/seed_incidents.py`:
   - Wrap CSV row iteration in `seed_incidents_from_csv` with per-record `try/except` to log bad records to `sys.stderr` and skip them without crashing the entire seeding run.
   - Replace broad `except Exception as e:` in `main()` with specific exception handling and explicit `sys.exit(1)` calls on critical failure.
3. In `services/api/seed.py`:
   - Wrap `run_seed()` in a `try/except` block and invoke `sys.exit(1)` if database operations fail.

### Rationale
- CLI scripts must signal failure to shell environments and CI/CD pipelines via standard non-zero exit codes (`1` for errors, `130` for Ctrl+C interrupt).
- Diagnostic messages should be sent to `sys.stderr` rather than mixed with standard data output on `sys.stdout`.

### Alternatives Considered
- **Ignoring Row Errors in CSV Seeding**: Could lead to silent data corruption without developer visibility. Logging skipped rows to `stderr` provides complete traceability.
