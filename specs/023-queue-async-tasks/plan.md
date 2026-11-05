# Implementation Plan: Queue Messages & Async Tasks

**Branch**: `feature/redis-celery-async-queue-task` | **Date**: 2026-11-05 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/023-queue-async-tasks/spec.md)

**Input**: Feature specification from `/specs/023-queue-async-tasks/spec.md`

---

## Summary

Decouple resource-intensive operations from the primary FastAPI service by introducing an asynchronous distributed task queue using Celery backed by Redis in Docker. Four target endpoints (`POST /reporting/trigger`, `GET /inventory/products`, `GET /telemetry/report`, `POST /incidents/analyze`) are converted to dispatch background tasks and immediately return an HTTP 202 Accepted response with a unique `task_id` in under 200ms. A dedicated status endpoint `GET /tasks/{task_id}` enables clients to poll task lifecycle states (`pending`, `started`, `success`, `failure`) and retrieve computed results while reliably returning HTTP 404 for invalid/unregistered identifiers. Transient task errors automatically retry up to 3 times with exponential backoff; failures exceeding 3 attempts are quarantined in a relational Dead Letter Queue (DLQ) database table with sanitized diagnostic metadata. Workers execute as separate operating system processes/containers, completely independent of the FastAPI web server, with real-time operational visibility provided via a Flower monitoring dashboard on port 5555.

---

## Technical Context

**Language/Version**: Python 3.11+ / Python 3.14 (FastAPI service in `services/api`)

**Primary Dependencies**: Celery (`celery[redis]>=5.3.0`), Redis (`redis>=5.0.0`), FastAPI (`fastapi>=0.100.0`), Pydantic v2 (`pydantic>=2.0.0`), SQLModel (`sqlmodel>=0.0.22`), Flower (`flower>=2.0.0`), Python-Multipart (`python-multipart>=0.0.6`)

**Storage**: 
- **Message Broker & Result Store**: Redis 7 Alpine (`trackflow-redis`) on port 6379, configured with `--maxmemory-policy noeviction` and append-only persistence (`appendonly yes`). Broker index `db 0`, result backend index `db 1`.
- **Ephemeral Task Registration**: Redis string key `task_meta:{task_id}` (TTL 86,400s) to disambiguate active pending jobs from arbitrary unknown UUIDs (enabling deterministic HTTP 404 responses).
- **Persistent Dead Letter Queue (DLQ)**: Relational database table `dead_letter_queue` in SQLite (`services/api/inventory.db`) and PostgreSQL via SQLModel adapter.
- **Transient Upload Staging**: Shared filesystem volume (`data/staging/incidents/`) for temporary disk storage of multi-megabyte incident CSV uploads before worker parsing.

**Testing**: `pytest` test suites (`services/api/tests/test_celery_tasks.py`, `services/api/tests/test_tasks_api.py`, `services/api/tests/test_celery_dlq.py`) validating synchronous validation, asynchronous dispatch, lifecycle state polling, retry backoff, DLQ quarantine, and error sanitization.

**Target Platform**: Linux server / Docker container / Windows host (multi-container topology in `docker-compose.yml`: `redis`, `backend`, `worker`, and `flower`).

**Project Type**: Asynchronous Distributed Queue Infrastructure & Web API Integration.

**Performance Goals**:
- Offloaded API endpoints return HTTP 202 Accepted with `task_id` in `< 200ms` (SC-001).
- Main FastAPI web server maintains zero thread starvation or request timeouts during heavy computational loads (SC-002).
- Status inspection `GET /tasks/{task_id}` responds in `< 15ms` from Redis cache.

**Constraints**:
- **Lightweight Queue Messages**: Broker messages MUST NOT contain raw CSV files, large data arrays, or binary payloads; only references, identifiers, or staging file paths (`< 64KB`) (FR-004).
- **At-Least-Once Delivery & Late Acknowledgement**: Worker acknowledgments (`ACK`) are deferred until task completion or until failure is committed to the DLQ (`task_acks_late = True`, `task_reject_on_worker_lost = True`).
- **Strict Retry Bound & DLQ Quarantine**: Tasks retry at most 3 times with exponential backoff ($2^{\text{retries}}$ seconds); 100% of tasks exceeding 3 failures are quarantined in `dead_letter_queue` (FR-007, FR-008, SC-003).
- **Zero Sensitive Data Leaks**: Zero tokens, passwords, or PII exposed in error strings, logs, or DLQ audit records (Constitution Principle IV).
- **Process Decoupling**: Stopping, restarting, or upgrading the web server process must never terminate active workers or discard enqueued broker messages (FR-012, SC-006).

**Scale/Scope**: 4 offloaded endpoints + 1 new task lifecycle endpoint + 1 DLQ entity + 1 base task class + 3 Docker services (`redis`, `worker`, `flower`).

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Plan Status | Justification / Validation |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Monorepo architectural boundaries MUST be strictly preserved. Frontend decoupled from DB; domain logic in `services/`; queue infrastructure isolated. | **PASS** | Celery configuration, worker factory, and task definitions reside within `services/api/infrastructure/queue/`. Presentation routers in `services/api/presentation/api/v1/` act strictly as HTTP controllers dispatching to the queue adapter. Shared DTOs and models remain cleanly separated. |
| **II. Public API Compatibility & Strict Contract Serialization** | 100% of FastAPI endpoints declare explicit `response_model`, typed parameters, and status codes. No internal tracebacks leaked. | **PASS** | Converted endpoints return explicit `AsyncTaskAcceptedResponse` (HTTP 202). `GET /tasks/{task_id}` declares `TaskStatusResponse` (HTTP 200) and structured HTTP 404/503 errors. Output payloads are projected through dedicated Pydantic schemas. |
| **III. Strict TypeScript & Static Type Safety** | Zero `any` types; explicit return type annotations and complete docstrings. | **PASS** | All new and modified Python modules strictly enforce explicit type hints, Pydantic v2 schemas, and comprehensive JSDoc/docstrings. Zero type suppression. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw error exposure; zero PII or credential leakage in logs or responses; no swallowed exceptions. | **PASS** | All task failures and exception messages pass through `sanitize_error_message()`, stripping bearer tokens, secrets, and masking email addresses before storing in the DLQ or returning via `GET /tasks/{task_id}`. |
| **V. Performance-First Architecture & Core Web Vitals** | Web applications maintain fast response times; eliminate long tasks. | **PASS** | Offloading long-running ETL, inventory stock calculations, telemetry queries, and CSV parsing from the web server thread pool to Celery workers guarantees that HTTP requests return in under 200ms, completely eliminating API thread starvation. |
| **VI. Test-First Development & Deterministic Verification Gates** | Reliability guaranteed through automated tests; passes `pytest`. | **PASS** | Comprehensive unit and integration test suites cover instant 202 response, lifecycle state transitions, exponential backoff retries, DLQ database insertion, and container decoupling. |

*Gate Evaluation: ALL GATES PASS.*

---

## Project Structure

### Documentation (this feature)

```text
specs/023-queue-async-tasks/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output: decisions on Redis broker, Celery worker, DLQ, file staging
├── data-model.md        # Phase 1 output: Task Message Envelope, Redis task_meta, DLQ SQLModel, DTOs
├── quickstart.md        # Phase 1 output: runnable validation scenarios
├── contracts/           # Phase 1 output: interface contracts
│   ├── tasks-api-contract.md
│   ├── async-endpoints-contract.md
│   └── dlq-contract.md
└── checklists/          # Validation checklists
```

### Source Code (repository root)

```text
services/api/
├── infrastructure/
│   └── queue/
│       ├── __init__.py          # Exports celery_app, TrackFlowTask, TaskStatusEnum
│       ├── celery_app.py        # Celery instance, Redis broker/backend configuration, task discovery
│       ├── custom_task.py       # TrackFlowTask base class: 3x retry, backoff, on_failure -> DLQ handler
│       ├── dlq.py               # DLQ persistence adapter & error sanitizer (masks tokens/PII)
│       ├── models.py            # SQLModel DeadLetterQueueRecord entity definition
│       └── tasks.py             # Celery task definitions (trigger_pipeline, list_products, etc.)
├── presentation/
│   └── api/
│       └── v1/
│           ├── tasks.py         # Router for GET /tasks/{task_id} (status & result retrieval)
│           ├── inventory.py     # Converted GET /inventory/products -> returns HTTP 202
│           ├── telemetry.py     # Converted GET /telemetry/report -> returns HTTP 202
│           └── incidents.py     # Converted POST /incidents/analyze -> stages file, returns HTTP 202
├── main.py                      # Mounts tasks router at /api/v1/tasks and /tasks
├── requirements.txt             # Added celery[redis], redis, flower
└── tests/
    ├── test_celery_tasks.py     # Unit tests for Celery task functions and worker logic
    ├── test_tasks_api.py        # Tests for GET /tasks/{task_id} lifecycle polling & 404 handling
    └── test_celery_dlq.py       # Tests for retry exponential backoff & DLQ database recording

services/reporting/
└── presentation/
    └── routes.py                # Converted POST /reporting/trigger -> returns HTTP 202 with task_id

data/
└── staging/
    └── incidents/               # Shared staging directory for uploaded incident CSVs (.gitignore'd)

docker-compose.yml               # Added redis (port 6379), worker, and flower (port 5555) services
```

**Structure Decision**: 
The solution adheres directly to the existing monorepo hexagonal architecture. The asynchronous queue is treated as an infrastructure adapter inside `services/api/infrastructure/queue/`. Presentation route handlers in `services/api/presentation/api/v1/` and `services/reporting/presentation/` accept client requests, synchronously validate incoming parameters/files, dispatch tasks to Celery via Redis, and return an immediate HTTP 202 response. The Celery worker runs as an independent operating system process/container consuming from the same Redis broker.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | Architectural design strictly complies with Monorepo Constitution Principles I through VI. | In-memory queues or background threads (e.g. `BackgroundTasks`) would be terminated on server restart and cannot scale independently across containers, violating FR-001 and FR-012. |
