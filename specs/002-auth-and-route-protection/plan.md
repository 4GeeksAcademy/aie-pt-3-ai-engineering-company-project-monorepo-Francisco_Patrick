# Implementation Plan: Auth & Route Protection

**Branch**: `[002-auth-and-route-protection]` | **Date**: 2026-09-07 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/002-auth-and-route-protection/spec.md)

**Input**: Feature specification from `/specs/002-auth-and-route-protection/spec.md`

## Summary

Implement stateless JWT-based authentication and route protection using FastAPI dependencies, storing User and Profile records exclusively in TinyDB. The module provides full CRUD for user credentials and profiles, a login endpoint returning signed tokens, and a reusable `get_current_user` dependency applied to sensitive routes.

## Technical Context

**Language/Version**: Python

**Primary Dependencies**: FastAPI, python-jose[cryptography], libpass[bcrypt]

**Storage**: TinyDB (for Users and Profiles)

**Testing**: pytest

**Target Platform**: Backend API service

**Project Type**: web-service

**Performance Goals**: Standard API performance

**Constraints**: Stateless JWT auth only (no sessions or cookies). Passwords MUST be hashed with bcrypt. User and Profile must stay in TinyDB even when Supabase is introduced.

**Scale/Scope**: Local API auth, protecting at least 5 existing sensitive routes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No specific constitutional violations detected. The project uses standard libraries and existing infrastructure (TinyDB).

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-and-route-protection/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
services/api/
├── domain/
│   ├── models.py                  # User, Profile domain entities
│   ├── ports.py                   # Repository and Security interfaces
│   └── exceptions.py              # Domain-specific exceptions
├── application/
│   └── services/                  # Use cases (AuthService, UserService)
├── infrastructure/
│   ├── adapters/
│   │   ├── tiny_db_repository.py  # TinyDB implementation of DB ports
│   │   └── security_adapter.py    # JWT/hashing implementation
│   └── database.py                # TinyDB connection setup
├── presentation/
│   ├── api/
│   │   ├── auth_routes.py         # Login & auth endpoints
│   │   ├── user_routes.py         # Users CRUD endpoints
│   │   └── profile_routes.py      # Profiles CRUD endpoints
│   └── dependencies.py            # FastAPI get_current_user
└── main.py                        # FastAPI app, wiring of adapters to services
```

**Structure Decision**: A strict Hexagonal (ports-adapters) architecture pattern to decouple core business logic (`domain/`, `application/`) from external concerns like the database or web framework (`infrastructure/`, `presentation/`).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
