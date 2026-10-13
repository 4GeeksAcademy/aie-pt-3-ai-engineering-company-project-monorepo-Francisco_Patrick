# Implementation Plan: Centralized Incident Manager - Backend

**Branch**: `006-centralized-incident-manager-backend` | **Date**: 2026-09-13 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/006-centralized-incident-manager-backend/spec.md)

**Input**: Feature specification from `/specs/006-centralized-incident-manager-backend/spec.md`

## Summary

Implement the backend management endpoints (`POST /api/incidents`, `GET /api/incidents`, `GET /api/incidents/{id}`, `PATCH /api/incidents/{id}/status`, `GET /api/incidents/summary`) with status lifecycle state machine enforcement (`open` -> `in_progress`/`discarded`, `in_progress` -> `resolved`/`discarded`, terminal: `resolved`/`discarded`), multi-attribute query filtering (`status`, `origin`, `branch`, `category`), 4-dimension summary metrics (`status`, `category`, `origin`, `branch`), and centralized HTTP 400 / 404 / 500 error handling preventing raw stack traces.

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI backend)

**Primary Dependencies**: FastAPI, Pydantic, TinyDB

**Storage**: TinyDB (`services/api/infrastructure/db.json`) with `incidents` table

**Testing**: Pytest & FastAPI TestClient for endpoint integration tests

**Target Platform**: Linux / Windows / Monorepo deployment environment

**Project Type**: Web API Service (`services/api`)

**Performance Goals**: API response time <50ms for query, detail, and status transition operations

**Constraints**: Strict lifecycle state transitions; HTTP 400 validation error responses identifying problematic fields; zero raw stack trace leaks; empty DB resilience for all read & summary endpoints

**Scale/Scope**: Operations dashboard API supporting multi-branch incident workloads

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Shared Domain Core**: Domain model state machine and schemas encapsulated in `domain/` and `shared/incidents/`. (PASSED)
- **Error Observability & Security**: Centralized error middleware returning clean JSON without stack traces. (PASSED)
- **Test-First / Verification**: Integration unit and contract tests verifying lifecycle state transitions and filtering. (PASSED)

## Project Structure

### Documentation (this feature)

```text
specs/006-centralized-incident-manager-backend/
├── plan.md              # Implementation plan
├── research.md          # Technical research & state machine design
├── data-model.md        # State transition matrix & DTO schemas
├── quickstart.md        # Runnable verification guide
└── contracts/
    └── management-api.md# API endpoints & error response schemas
```

### Source Code (repository root)

```text
shared/
└── incidents/           # Shared enums and transformation logic

services/api/
├── domain/
│   ├── incident_model.py# Incident entity & state machine transition guard
│   ├── exceptions.py    # Custom domain exceptions (InvalidStatusTransition, IncidentNotFound)
│   └── schemas/
│       └── incident_schema.py # Request / Response Pydantic schemas
├── infrastructure/
│   └── adapters/
│       └── tiny_db_incident_repository.py # TinyDB filtering & 4-dimension summary counts
├── application/
│   └── services/
│       └── incident_service.py # Application logic (create, list, get, transition, summary)
├── presentation/
│   └── api/
│       └── incident_routes.py # Route handlers (POST, GET, GET /{id}, PATCH /{id}/status, GET /summary)
└── main.py              # Application entrypoint & exception handlers
```

**Structure Decision**: Integrated within `services/api` following clean layered architecture (domain, infrastructure, application, presentation).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations detected. Implementation adheres strictly to existing architecture.*
