# Research & Architectural Decisions: Queue Messages & Async Tasks

**Feature**: Queue Messages & Async Tasks via Celery and Redis  
**Branch**: `feature/redis-celery-async-queue-task` (`023-queue-async-tasks`)  
**Date**: 2026-11-05  

---

## 1. Message Broker & In-Memory Eviction Policy

### Decision
Deploy **Redis 7 (Alpine)** as the centralized message broker and Celery result backend via Docker container (`trackflow-redis`) on port 6379, configured with `--maxmemory-policy noeviction` and append-only persistence (`appendonly yes`). Broker connection URL is injected via `REDIS_URL` with defaults `redis://localhost:6379/0` (local development) and `redis://redis:6379/0` (Docker internal network `trackflow-net`). Result backend is configured on database index 1 (`redis://.../1`).

### Rationale
- **No Eviction Guarantee**: Celery broker queues rely on Redis List and Stream data structures. If memory capacity is saturated, the `noeviction` policy returns errors on new task insertion rather than silently dropping or evicting pending task messages, preventing silent message loss.
- **Unified Broker & Result Backend**: Redis provides sub-millisecond round-trip latency for both task dispatch and status querying, avoiding the need for two separate services (e.g. RabbitMQ for broker and PostgreSQL for results).
- **Docker Integration**: Fits existing `docker-compose.yml` infrastructure topology cleanly alongside `trackflow-backend` and `trackflow-ui`.

### Alternatives Considered
- **RabbitMQ**: Excellent AMQP broker with native DLQ capabilities, but requires higher memory footprint, Erlang runtime, and distinct result backend infrastructure. Rejected to maintain lean container footprint.
- **In-Memory Celery (`memory://`)**: Only works inside a single process; does not support independent worker processes across operating system boundaries. Rejected because FR-001/SC-006 mandates independent worker execution.
- **Redis with `allkeys-lru` eviction**: Dangerous for message brokers; would silently discard waiting tasks under memory pressure. Rejected in favor of `noeviction`.

---

## 2. Celery Application Structure & Hexagonal Boundaries

### Decision
Encapsulate the Celery configuration, worker entry point, and task definitions within `services/api/infrastructure/queue/`:
- `celery_app.py`: Celery instance factory and configuration.
- `tasks.py`: Task definitions wrapping domain services (`trigger_pipeline_task`, `list_products_task`, `telemetry_report_task`, `analyze_incidents_task`).
- `dlq.py`: Dead Letter Queue persistence handler and models.
- `custom_task.py`: Custom base task class `TrackFlowTask` implementing retry limits, exponential backoff, structured event logging, and DLQ dispatch upon final failure.

The API presentation layer dispatches tasks using Celery `.delay()` or `.apply_async()` and returns HTTP 202 Accepted.

### Rationale
- **Hexagonal Architecture (Constitution Principle I)**: Celery is an infrastructure adapter (queueing mechanism). Presentation routes remain controllers that parse HTTP input, invoke the queue adapter, and return standard Pydantic response models.
- **Reusable Worker Process**: Independent worker processes execute via `celery -A services.api.infrastructure.queue.celery_app worker -l INFO -c 2`, loading task definitions without starting the FastAPI web server.

### Alternatives Considered
- **Inline Celery initialization in `services/api/main.py`**: Violates Single Responsibility and creates cyclic imports when worker processes import `main.py` (which boots FastAPI, middleware, and route mounting).
- **FastAPI BackgroundTasks**: Executes inside the web server process; stopped if the web process restarts and cannot scale independently. Rejected because FR-001/FR-012 mandates process separation.

---

## 3. Task Status Tracking & Non-Existent Task Resolution (HTTP 404)

### Decision
Expose `GET /tasks/{task_id}` via a dedicated presentation router (`services/api/presentation/api/v1/tasks.py`) mounted at `/api/v1/tasks` and `/tasks`.
To distinguish between **truly pending tasks** and **non-existent tasks** (since Celery default Redis backend returns `PENDING` for any arbitrary unknown UUID):
1. When any endpoint enqueues a task, it sets a lightweight metadata key in Redis (`task_meta:{task_id}`) with status `pending`, task name, and enqueue timestamp (with TTL 86400s / 24h).
2. When querying `GET /tasks/{task_id}`, the endpoint inspects `task_meta:{task_id}` or `AsyncResult(task_id)`:
   - If no task metadata exists in Redis and Celery state is `PENDING`, the task is unknown -> return HTTP 404 Not Found (`{"detail": "Task '{task_id}' not found"}`).
   - If found, query `AsyncResult(task_id).state`:
     - `PENDING` -> return `{"task_id": "...", "status": "pending", "result": null, "error": null}`
     - `STARTED` -> return `{"task_id": "...", "status": "started", "result": null, "error": null}`
     - `SUCCESS` -> return `{"task_id": "...", "status": "success", "result": res.result, "error": null}`
     - `FAILURE` -> return `{"task_id": "...", "status": "failure", "result": null, "error": sanitized_error}`

### Rationale
- **Solves the Celery Ghost Task Problem**: In Celery with Redis backend, querying an unsubmitted UUID `AsyncResult("random-uuid").state` returns `"PENDING"`. By registering the submission key atomically upon dispatch, the API can deterministically return HTTP 404 for fabricated IDs while returning `pending` for real jobs in queue.
- **Meets Acceptance Scenario 2.4**: Validates SC-004 and AC 2.4 without leaking internal broker details.

### Alternatives Considered
- **SQL Database write on every enqueue**: High database write contention under high request rates. Using Redis key with 24-hour expiration keeps task tracking fast (< 2ms) and ephemeral.
- **Accepting `PENDING` for all IDs**: Violates AC 2.4 which strictly requires HTTP 404 for non-existent task IDs.

---

## 4. Large Payload Staging for File Uploads (`/incidents/analyze`)

### Decision
When a multipart CSV file is uploaded to `POST /incidents/analyze`:
1. The presentation route performs initial synchronous validation (file extension check, non-empty check, basic character encoding inspection) before enqueueing.
2. The route streams the file content to a shared temporary staging directory (`data/staging/incidents/{task_id}.csv`).
3. The enqueued Celery task receives only the staged file path (`data/staging/incidents/{task_id}.csv`) and metadata (original filename, size).
4. The background worker parses the staged CSV from disk, processes the report, stores the result, and removes/archives the staged file upon task completion.

### Rationale
- **Broker Memory Protection (FR-004 & AC 1.2)**: Passing multi-megabyte CSV files directly as Celery message arguments causes memory ballooning in Redis and degrades message throughput.
- **Fail-Fast Validation**: Malformed file extensions or empty files are rejected with HTTP 400 immediately at the HTTP boundary, avoiding unnecessary worker queue cycles.

### Alternatives Considered
- **Base64 encoding file contents into Celery message body**: Simple to implement but inflates message size by ~33% and places heavy serialization burden on Redis. Rejected.
- **Direct S3 / Object Store bucket**: Ideal for multi-node production clusters, but introduces external cloud dependencies for local development. A local shared volume `data/staging/` mounted into both API and worker containers works identically in local development and Docker.

---

## 5. Resilient Retry Strategy & Dead Letter Queue (DLQ) Persistence

### Decision
Implement a custom Celery Task class (`TrackFlowTask`) inheriting from `celery.Task`:
- **Retry Policy**:
  - `autoretry_for = (Exception,)`
  - `max_retries = 3`
  - `retry_backoff = True` (exponential backoff: 2s, 4s, 8s)
  - `retry_jitter = True` (prevents thundering herd)
  - `task_acks_late = True` (task acknowledged only after execution completes or DLQ handoff)
  - `task_reject_on_worker_lost = True` (re-queues task if worker process terminates abruptly)
- **Dead Letter Queue (DLQ) Recording**:
  - Upon failure where `request.retries >= 3` (or upon unrecoverable exception), Celery's `on_failure` hook triggers.
  - A record is persisted to the relational database table `dead_letter_queue` via SQLModel adapter:
    - `id`: Auto-incrementing primary key
    - `task_id`: String UUID
    - `task_name`: Full task identifier (e.g. `services.api.infrastructure.queue.tasks.analyze_incidents_task`)
    - `attempt_number`: Final attempt count (3)
    - `error_message`: Sanitized error summary (PII/secrets scrubbed, truncated to 500 characters)
    - `payload_reference`: Staging file path or parameter summary
    - `failed_at`: UTC timestamp
  - The Celery message is acknowledged (`ACK`) only after the DLQ database insertion succeeds, ensuring zero unrecorded drops.

### Rationale
- **AC 3.2 & FR-008 Compliance**: Guarantees that failing tasks do not loop infinitely and leaves an auditable trace in the central relational database (`inventory.db` / PostgreSQL).
- **At-Least-Once Delivery**: `task_acks_late=True` prevents task loss if a worker dies mid-execution.

### Alternatives Considered
- **Separate Redis DLQ List (`celery_dlq`)**: Retains raw task bodies in Redis, but is ephemeral and hard to query with SQL alongside other operational models. Relational persistence provides ACID storage and easy admin inspection.

---

## 6. Queue Observability & Monitoring with Flower

### Decision
Add a `flower` service container to `docker-compose.yml`:
```yaml
flower:
  build:
    context: .
    dockerfile: services/Dockerfile
  container_name: trackflow-flower
  command: celery -A services.api.infrastructure.queue.celery_app flower --port=5555 --basic_auth=${FLOWER_BASIC_AUTH:-}
  ports:
    - "5555:5555"
  environment:
    - REDIS_URL=${REDIS_URL:-redis://redis:6379/0}
  depends_on:
    - redis
  networks:
    - trackflow-net
  restart: unless-stopped
```

### Rationale
- **FR-010 & SC-005 Compliance**: Provides out-of-the-box real-time visibility into active workers, pending tasks, task history, and runtime latency on port 5555 during development.

### Alternatives Considered
- **Custom Prometheus / Grafana exporter**: High operational overhead for development environments. Flower provides a complete interactive dashboard with zero custom frontend code.

---

## 7. Security, PII Masking, and Defensive Error Handling (Constitution Principle IV)

### Decision
1. Sanitize all error strings before storing in Celery result backend or `dead_letter_queue`:
   - Mask email addresses (`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b`).
   - Mask authorization tokens and secret keys (`bearer\s+[a-zA-Z0-9_\-\.]+`, `secret_[a-zA-Z0-9]+`).
   - Strip internal file paths and system tracebacks from client-visible error responses.
2. In `GET /tasks/{task_id}`, return a sanitized error message if task failed, avoiding raw internal exception propagation.
3. Validate all incoming parameters with Pydantic schemas before pushing tasks to the broker.

### Rationale
- Fully adheres to Monorepo Constitution Principle IV ("Defensive Error Handling & Zero Sensitive Data Leaks") and Principle II ("Strict Contract Serialization").

