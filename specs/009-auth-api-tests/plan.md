# Implementation Plan: FastAPI Backend Authentication API Unit Testing

**Branch**: `009-auth-api-tests` | **Date**: 2026-09-13 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/009-auth-api-tests/spec.md)

**Input**: Feature specification from `/specs/009-auth-api-tests/spec.md`

## Summary

Add a comprehensive unit and business logic test battery for the FastAPI Authentication API (`services/api/`) covering specs 002 and 004, alongside Jest tests for TypeScript authentication utilities (`uis/backoffice/lib/auth.ts`, `lib/authApi.ts`). The test suite focuses strictly on business logic (credential validation, JWT creation/decoding, active user filtering, password reset single-use tokens, rate-limiting, anti-enumeration) and enforces >= 70% backend code coverage verified via `uv run pytest --cov`. The test strategy and AI-assisted workflow are documented in root `TESTING.md`.

## Technical Context

**Language/Version**: Python >= 3.14 (Backend), TypeScript 5.x / Node.js (Frontend)

**Primary Dependencies**: `FastAPI`, `pytest`, `pytest-cov`, `httpx`, `passlib`/`libpass`, `python-jose`, `Jest`

**Storage**: In-memory TinyDB instance for test execution isolation

**Testing**: `uv run pytest` (Python), `jest --coverage` (TypeScript)

**Target Platform**: Cross-platform (Windows / Linux) backend service & Next.js UI workspace

**Project Type**: Web service API + Web application library

**Performance Goals**: Test suite execution completes under 5 seconds

**Constraints**: Business logic focus (no serialization / framework plumbing tests); minimum 70% backend code coverage; 1 Happy Path, 1 Edge Case, 1 Failure Mode per endpoint.

**Scale/Scope**: 6 API endpoints (`/auth/login`, `/auth/me`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`, `/users`), 2 domain services (`AuthService`, `JwtSecurityAdapter`), 2 TypeScript utilities (`auth.ts`, `authApi.ts`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Test-First & Logic Focus**: Tests assert business logic and domain rules directly.
- [x] **Coverage & Quality Gates**: Target >= 70% coverage on authentication modules.
- [x] **Documentation Standards**: Root `TESTING.md` updated with execution commands, test matrix, and AI workflow notes.

## Project Structure

### Documentation (this feature)

```text
specs/009-auth-api-tests/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── contracts/           # Phase 1 output
    └── auth-test-contract.md
```

### Source Code (repository root)

```text
services/api/
├── application/services/
│   └── auth_service.py
├── infrastructure/adapters/
│   └── security_adapter.py
├── presentation/api/
│   ├── auth_routes.py
│   └── user_routes.py
└── tests/               # Python backend test battery
    ├── unit/
    │   ├── test_security_adapter.py
    │   └── test_auth_service.py
    └── api/
        ├── test_login_api.py
        ├── test_me_api.py
        ├── test_password_reset_api.py
        ├── test_change_password_api.py
        └── test_user_registration_api.py

uis/backoffice/
├── lib/
│   ├── auth.ts
│   └── authApi.ts
└── __tests__/           # TypeScript Jest test battery
    ├── auth.test.ts
    └── authApi.test.ts

TESTING.md               # Root test strategy and execution documentation
```

**Structure Decision**: Monorepo split between `services/api/tests/` for Python pytest suites and `uis/backoffice/__tests__/` for Jest TypeScript tests, matching existing project architecture.

## Complexity Tracking

*No constitution violations present.*
