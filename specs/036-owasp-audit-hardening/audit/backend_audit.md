# OWASP Top 10 Security Audit: Backend Services

**Evaluated Target**: TrackFlow Backend API Service (`services/api/`)  
**Architecture**: FastAPI REST Service, SQLModel ORM, TinyDB adapter, Redis broker, JWT auth  
**Evaluator**: TrackFlow Security Engineering  
**Evaluation Date**: 2026-11-25  
**Commit**: `8f4091add62f74d3e578cc5d60f605e75df9d789` | **Branch**: `feature/owasp-top10-audit`

---

## 1. Executive Summary

A comprehensive assessment of the TrackFlow backend API was conducted against the **OWASP Top 10 (2021)** standard. The audit identified two **CRITICAL** vulnerabilities requiring immediate remediation:
1. **Permissive CORS Wildcard with Credentials** (`services/api/main.py:95-99`): `allow_origins=["*"]` configured alongside `allow_credentials=True`. This creates severe cross-origin vulnerability exposure where untrusted web domains can access authenticated session APIs.
2. **Raw Exception Exposure & Leakage** (`services/api/core/exceptions.py`): Default error handlers leaking runtime traces or unhandled raw exception text (`str(e)`) in violation of Constitution Principle IV and OWASP A09.

All findings, applicability verdicts, severity levels, and remediation blueprints are detailed below.

---

## 2. Findings Matrix

| Finding ID | OWASP Category | Finding Title | Severity | Applicability | Status |
|---|---|---|---|---|---|
| `SEC-BK-001` | A01: Broken Access Control | Horizontal IDOR on Incident & Order Endpoints | HIGH | APPLIES | OPEN |
| `SEC-BK-002` | A02: Cryptographic Failures | Hardcoded Fallback Secrets & Permissive JWT Lifetimes | HIGH | APPLIES | OPEN |
| `SEC-BK-003` | A03: Injection | SQLModel Parameterized Query Validation | LOW | DOES_NOT_APPLY | MITIGATED |
| `SEC-BK-004` | A04: Insecure Design | Absence of Rate Limiting on Authentication Routes | MEDIUM | APPLIES | OPEN |
| `SEC-BK-005` | A05: Security Misconfiguration | Permissive CORS Wildcard with Credentials Enabled | CRITICAL | APPLIES | VERIFIED_RESOLVED |
| `SEC-BK-006` | A06: Vulnerable Components | Unpinned Transitive Dependencies in pyproject.toml | LOW | APPLIES | OPEN |
| `SEC-BK-007` | A07: Identification & Auth Failures | Missing Refresh Token Rotation and Invalidation | MEDIUM | APPLIES | OPEN |
| `SEC-BK-008` | A08: Software & Data Integrity Failures | Unsigned Webhook Payloads for External Ingestion | MEDIUM | APPLIES | OPEN |
| `SEC-BK-009` | A09: Logging & Monitoring Failures | Sensitive Credentials & Raw Exception Traces in Logs | CRITICAL | APPLIES | VERIFIED_RESOLVED |
| `SEC-BK-010` | A10: Server-Side Request Forgery | Outbound HTTP Webhook & Telemetry Client Dispatch | LOW | DOES_NOT_APPLY | MITIGATED |

---

## 3. Detailed Category Evaluations

### SEC-BK-001: A01 Broken Access Control
- **Location**: `services/api/presentation/api/v1/incidents.py` & `inventory.py`
- **Applicability**: `APPLIES`
- **Description**: Certain query handlers perform entity lookups by identifier without strictly verifying that the authenticated user's organization or customer ID owns the target incident.
- **Remediation**: Enforce organization-level tenant filters across all SQLModel queries and dependency injection checks.

### SEC-BK-002: A02 Cryptographic Failures
- **Location**: `services/api/infrastructure/security/jwt_adapter.py`
- **Applicability**: `APPLIES`
- **Description**: Default fallback strings for JWT signing keys in development configurations risk production deployment exposure if environment validation fails.
- **Remediation**: Fail-fast on service startup if `JWT_SECRET_KEY` is empty, unset, or equal to development defaults.

### SEC-BK-003: A03 Injection
- **Location**: `services/api/infrastructure/persistence/sqlmodel/`
- **Applicability**: `DOES_NOT_APPLY`
- **Description**: The service strictly utilizes SQLModel / SQLAlchemy ORM parameterized statements with typed Pydantic models. No raw string interpolation or untyped SQL execution is present.
- **Remediation**: Architectural mitigation maintained by ORM governance.

### SEC-BK-004: A04 Insecure Design
- **Location**: `services/api/presentation/api/v1/auth.py`
- **Applicability**: `APPLIES`
- **Description**: Lack of IP-based or account-based rate limiting on login and password reset routes permits brute-force credential stuffing.
- **Remediation**: Introduce Redis-backed sliding-window rate limiters on `/api/v1/auth/login` and `/api/v1/auth/reset-password`.

### SEC-BK-005: A05 Security Misconfiguration (CRITICAL)
- **Location**: `services/api/main.py:93-99`
- **Applicability**: `APPLIES`
- **Severity**: `CRITICAL`
- **Description**: `CORSMiddleware` is configured with `allow_origins=["*"]` and `allow_credentials=True`. This allows arbitrary cross-origin web apps to issue authenticated requests with cookies/credentials, violating browser cross-origin policy and OWASP A05.
- **Remediation Plan**: Replace wildcard origin with explicit `CORS_ALLOWED_ORIGINS` loaded from environment variables, defaulting to approved frontend origins (`http://localhost:3000`, `http://localhost:3001`, `https://app.trackflow.io`).
- **Verification Proof**: Automated test in `services/api/tests/unit/test_security_cors_configuration.py` confirming rejection of untrusted origins.

### SEC-BK-006: A06 Vulnerable and Outdated Components
- **Location**: `services/api/pyproject.toml`
- **Applicability**: `APPLIES`
- **Description**: Some package dependencies specify loose lower bounds without upper bounds, leaving builds susceptible to breaking upstream updates or supply-chain compromises.
- **Remediation**: Lock lockfiles using `uv lock` and configure automated vulnerability scanning (`pip-audit` / Dependabot).

### SEC-BK-007: A07 Identification & Authentication Failures
- **Location**: `services/api/presentation/api/v1/auth.py`
- **Applicability**: `APPLIES`
- **Description**: Access tokens cannot be revoked before natural expiration; no token revocation denylist is maintained.
- **Remediation**: Implement a Redis token denylist for instant logout and session revocation.

### SEC-BK-008: A08 Software & Data Integrity Failures
- **Location**: `services/api/presentation/api/v1/telemetry.py`
- **Applicability**: `APPLIES`
- **Description**: Incoming telemetry payloads from external carriers are validated for schema but lack HMAC-SHA256 signature verification.
- **Remediation**: Introduce webhook signature verification headers for enterprise carrier endpoints.

### SEC-BK-009: A09 Security Logging & Monitoring Failures (CRITICAL)
- **Location**: `services/api/core/exceptions.py` & `services/api/application/services/guardrail_observability.py`
- **Applicability**: `APPLIES`
- **Severity**: `CRITICAL`
- **Description**: Unhandled exceptions exposed raw internal details (`str(e)`) in HTTP 500 error responses, potentially leaking database schema and stack traces to clients. Additionally, log outputs lacked masking for carrier secrets (UPS, FedEx, DHL, MRW, SEUR) and customer PII.
- **Remediation Plan**: Refactor FastAPI exception handlers to return sanitized error messages (verified via `test_error_handling_sanitization.py` against base implementation), and implement regex-based redaction in logging middleware.
- **Verification Proof**: Unit tests `test_error_handling_sanitization.py` and `test_guardrail_observability_redaction.py`.

### SEC-BK-010: A10 Server-Side Request Forgery (SSRF)
- **Location**: `services/api/infrastructure/adapters/`
- **Applicability**: `DOES_NOT_APPLY`
- **Description**: Outbound HTTP requests are strictly limited to pre-configured carrier API endpoints and Supabase / Qdrant cluster endpoints. No user-supplied URLs or endpoints are accepted for external fetching.
- **Remediation**: Architectural absence of user-controlled target URIs.
