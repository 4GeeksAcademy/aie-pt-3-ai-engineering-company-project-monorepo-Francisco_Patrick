# Implementation Plan: Automated Nightly Telemetry Export & Orchestration

**Branch**: `022-nightly-telemetry-export` | **Date**: 2026-10-27 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/022-nightly-telemetry-export/spec.md)

**Input**: Feature specification from `/specs/022-nightly-telemetry-export/spec.md`

## Summary

Implement an autonomous, resilient nightly background orchestration process that extracts the previous day's telemetry events, writes point-in-time audit snapshots to `data/raw/telemetry_YYYY-MM-DD.csv`, and triggers the executive analytical KPI pipeline as an isolated subprocess. The architecture enforces database-backed concurrency locking to prevent overlapping executions, per-date idempotency with safe date overrides (`TARGET_DATE`), and defensive error handling that cleanly transitions failed jobs to `failed` with sanitized diagnostics without leaving stranded `processing` locks. Persistence and domain logic are encapsulated within `services/jobs/`, and the CLI entry point resides in `scripts/nightly_export.py`. Existing telemetry assets (`services/telemetry/analysis.py` and `telemetry_events` table) remain 100% untouched.

---

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: SQLModel / SQLAlchemy (database ORM and connection pooling), Pandas (telemetry CSV extraction), Prefect 3.x (pipeline execution orchestration via subprocess), Pydantic v2 (schema validation)

**Storage**: PostgreSQL (production) with local SQLite fallback (`services/api/inventory.db`); `job_runs` table for execution state and concurrency locks; raw immutable CSV snapshots in `data/raw/telemetry_YYYY-MM-DD.csv`

**Testing**: `pytest` for unit and integration test suites (`tests/unit/jobs/`, `tests/integration/jobs/`)

**Target Platform**: Linux server / Docker container / Windows host (detached background process / cron executor)

**Project Type**: CLI orchestration tool (`scripts/nightly_export.py`) backed by internal domain service (`services/jobs/`)

**Performance Goals**: 
- 0ms latency impact on public web API endpoints (executes completely out-of-process).
- < 100ms lock check and idempotency verification.
- Fast, non-blocking telemetry extraction.

**Constraints**:
- Concurrency locking: secondary overlapping executions must detect active locks, log at `INFO`, and exit with code 0 without duplicate work.
- Idempotency: re-running completed dates must not overwrite existing CSVs or re-execute downstream pipelines.
- Zero stranded locks: all termination paths must ensure `processing` state transitions to `completed` or `failed`.
- Defensive logging: zero leakage of credentials, passwords, or PII; error messages sanitized and truncated to 500 characters.
- Non-interference: zero changes to `services/telemetry/analysis.py` or the schema/records of `public.telemetry_events`.

**Scale/Scope**: Daily batch processing of telemetry event records (10k-50k events/day); single isolated CLI subprocess per scheduled run.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Plan Status | Justification / Validation |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Monorepo architectural boundaries MUST be strictly preserved. Frontend decoupled from DB; domain logic in `services/`; scripts in `scripts/` isolated. Zero modifications to `services/telemetry/analysis.py` or `telemetry_events`. | **PASS** | Orchestrator domain logic and SQLModel models live in `services/jobs/`. CLI entry point lives in `scripts/nightly_export.py`. Downstream pipeline is invoked via an isolated subprocess. `services/telemetry/analysis.py` and `telemetry_events` remain untouched. |
| **II. Public API Compatibility & Serialization** | 100% FastAPI endpoints declare explicit `response_model`, no breaking changes to public APIs. | **PASS** | No public HTTP REST API routes are modified. This feature operates exclusively as a scheduled background CLI process and domain service. |
| **III. Strict TypeScript & Static Type Safety** | Zero `any` types; explicit return type annotations and JSDoc / docstrings. | **PASS** | Monorepo TypeScript is untouched. Python services enforce strict type hints on 100% of methods and functions, accompanied by docstrings. |
| **IV. Defensive Error Handling & Zero Leaks** | No raw tracebacks or secrets leaked; no swallowed exceptions (`except: pass`); clean state recovery. | **PASS** | `sanitize_error_message` masks sensitive credentials. Outer exception handlers transition job records to `failed` and exit with non-zero code. Zero jobs left stranded in `processing`. |
| **V. Performance-First Architecture** | Web apps maintain CWV targets; eliminate long tasks. | **PASS** | CLI process runs out-of-process in background, placing zero compute overhead on web server request loops. |
| **VI. Test-First Development & Quality Gates** | Comprehensive unit/integration tests; deterministic seeding; passes `pytest`. | **PASS** | Test plan provides full unit test coverage for lock checks, idempotency, date resolution, and error sanitization, plus integration tests for end-to-end runs. |

*Gate Evaluation: ALL GATES PASS.*

---

## Project Structure

### Documentation (this feature)

```text
specs/022-nightly-telemetry-export/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output: decisions on date parsing, locking, subprocess, retries
├── data-model.md        # Phase 1 output: job_runs schema, CSV layout, state machine
├── quickstart.md        # Phase 1 output: runnable validation scenarios
└── contracts/           # Phase 1 output: CLI and service contracts
    ├── cli-contract.md
    └── service-contract.md
```

### Source Code (repository root)

```text
services/
└── jobs/
    ├── __init__.py      # Exports NightlyExportRunner, JobRun, JobStatus, init_jobs_db
    ├── models.py        # SQLModel entity JobRun, table job_runs, index definitions, JobStatus
    └── runner.py        # NightlyExportRunner: date resolution, locking, export, subprocess

scripts/
└── nightly_export.py    # Autonomous CLI entry point with --date, --dry-run, --verbose flags

data/
└── raw/
    └── telemetry_YYYY-MM-DD.csv  # Point-in-time audit snapshot files (created on export)

tests/
├── unit/
│   └── jobs/
│       ├── __init__.py
│       └── test_nightly_export_runner.py  # Unit tests for date resolution, locking, idempotency
└── integration/
    └── jobs/
        ├── __init__.py
        └── test_nightly_export_e2e.py     # End-to-end export & pipeline execution tests
```

**Structure Decision**:
- Following Monorepo Constitution Principle I and FR-009, persistence and business logic are located under `services/jobs/`, while the autonomous CLI entry point is located in `scripts/nightly_export.py`.
- Source telemetry events are read from `public.telemetry_events` in read-only mode, writing CSV snapshots to `data/raw/telemetry_YYYY-MM-DD.csv`.
- The downstream analytics pipeline (`data/pipelines/pipeline.py`) is invoked via subprocess with start and end date parameters corresponding to the target date.

---

## Post-Design Constitution Re-Evaluation

Following the completion of Phase 1 design artifacts (`data-model.md`, `contracts/`, `quickstart.md`):

1. **Principle I (Service Boundaries)**: Verified. CLI in `scripts/`, domain logic in `services/jobs/`, downstream pipeline in `data/pipelines/`, existing telemetry untouched. **PASS**.
2. **Principle II (Public API)**: No public API modifications. **PASS**.
3. **Principle III (Type Hygiene)**: Explicit Python typing across `services/jobs/models.py` and `runner.py`. **PASS**.
4. **Principle IV (Defensive Error Handling)**: All failure paths capture exceptions, mask credentials, update `job_runs.error_message`, and guarantee no stranded `processing` locks. **PASS**.
5. **Principle V (Performance)**: Detached background execution ensures 0ms latency impact on web endpoints. **PASS**.
6. **Principle VI (Test Gates)**: Full unit and integration test coverage defined in `quickstart.md` and `tests/`. **PASS**.

---

## Complexity Tracking

> No constitution violations detected. Table kept empty as all designs comply with core principles.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | N/A |
