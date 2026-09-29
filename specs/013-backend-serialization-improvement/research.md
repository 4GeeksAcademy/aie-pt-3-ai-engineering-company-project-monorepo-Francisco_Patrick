# Research & Technical Decisions: Backend Serialization Improvement

**Feature Branch**: `013-backend-serialization-improvement`
**Date**: 2026-09-29
**Status**: Completed

## 1. Technical Decisions & Rationale

### Decision 1: DTO Projections for User Isolation & Credential Security
- **Decision**: Introduce explicit Pydantic response DTOs (`UserResponse`) in the presentation layer and decouple HTTP response serialization from internal domain entities (`domain.models.User`).
- **Rationale**: The internal `User` domain model stores `hashed_password: str` to facilitate authentication verification and database persistence. When route handlers used `response_model=User`, FastAPI serialized all fields present on the model into the outgoing JSON payload, leaking bcrypt/argon2 password hashes to client browsers and administrative callers. Creating `UserResponse(id, email, is_active, role, created_at)` strictly confines the output schema to public metadata.
- **Alternatives Considered**:
  - *`Field(exclude=True)` on domain `User` model*: Rejected because the password hash is needed during domain operations (verifying credentials against database records) and marking it excluded globally breaks domain conversions.
  - *FastAPI `response_model_exclude={"hashed_password"}` on route decorators*: Rejected because it is error-prone, easy to omit on future routes, and does not accurately document the output contract in OpenAPI specs.

### Decision 2: Standardized Operational Message Schemas
- **Decision**: Introduce a reusable `MessageResponse(message: str)` Pydantic schema for all operational confirmation endpoints (`/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`).
- **Rationale**: These endpoints previously returned untyped Python dictionaries (`{"message": "..."}`) without declaring `response_model`. Declaring `response_model=MessageResponse` ensures full OpenAPI contract coverage, validates outgoing payload shapes, and maintains anti-enumeration guarantees without reflecting client email addresses in responses.
- **Alternatives Considered**:
  - *HTTP 204 No Content*: Rejected because frontend client state handlers (and existing integration tests) consume the confirmation message string to display toast notifications and confirmation banners.

### Decision 3: Concrete Schema Definitions for Incident Analytics & Streams
- **Decision**: Introduce `IncidentSummaryResponse` for the aggregated multi-dimensional metrics endpoint (`GET /api/incidents/summary`) and `IncidentAnalysisResponse` with nested `IncidentMetrics` and `IncidentDiagnostics` for the stream ingestion endpoint (`POST /api/incidents/analyze`).
- **Rationale**: Previously, `GET /api/incidents/summary` declared a loose `Dict[str, Any]` and `POST /api/incidents/analyze` lacked a `response_model`. Providing concrete models guarantees typed dictionary keys, prevents accidental structural drift between backend and frontend analytics dashboards, and provides exhaustive OpenAPI documentation.
- **Alternatives Considered**:
  - *Dynamic schema generation*: Rejected in favor of static Pydantic models for compile-time/test-time validation.

### Decision 4: Safe Email Handling in Authentication & Profile Endpoints
- **Decision**:
  - `GET /auth/me`: Retain `email` in the `UserResponse` projection because authenticated user sessions and frontend profile components rely on displaying the current user's email.
  - `POST /users` (Registration) & Password Recovery flows (`/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`): Avoid echoing redundant email fields or sensitive token strings.
- **Rationale**: Balances user privacy and anti-enumeration protections with legitimate frontend application rendering requirements.

---

## 2. Dependency & Compatibility Analysis

- **FastAPI / Pydantic**: Pydantic v2 compatible (`model_config = ConfigDict(from_attributes=True)` or standard `BaseModel`).
- **Backward Compatibility**: All existing field names (`id`, `email`, `is_active`, `role`, `created_at`, `message`, `metrics`, `diagnostics`) remain identical. Existing frontend clients and automated pytest suites will continue functioning seamlessly without breaking changes.
