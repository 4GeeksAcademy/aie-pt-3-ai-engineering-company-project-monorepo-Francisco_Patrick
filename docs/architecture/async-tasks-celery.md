# Asynchronous Tasks & Distributed Queue Architecture: Celery & Redis

This document provides architectural and operational documentation for the asynchronous distributed task queue in TrackFlow.

---

## 1. Architectural Overview

To eliminate thread starvation and request latency on the central FastAPI web server, long-running computational workloads are offloaded to background Celery workers consuming from a Redis message broker.

```
+-------------------------------------------------------------------------------+
|                                  FastAPI API                                  |
|                                                                               |
|  POST /reporting/trigger                                                      |
|  GET  /inventory/products                                                     |
|  GET  /telemetry/report       ---> Enqueue Task ---> Return HTTP 202 Accepted |
|  POST /incidents/analyze                                 (with task_id)       |
+-------------------------------------------------------------------------------+
                                      |
                                      v
                     +---------------------------------+
                     |    Redis 7 (Port 6379)          |
                     |  - DB 0: Celery Broker Queue    |
                     |  - DB 1: Celery Result Backend  |
                     |  - Key: task_meta:{task_id}     |
                     +---------------------------------+
                                      |
                                      v
                     +---------------------------------+
                     |     Celery Background Worker    |
                     |  - Processes task in background |
                     |  - 3x exponential retry backoff |
                     |  - Late acknowledgement (ACK)   |
                     +---------------------------------+
                                      | (on 3rd failure)
                                      v
                     +---------------------------------+
                     |    Relational Database (DLQ)    |
                     |  - Table: dead_letter_queue     |
                     |  - Sanitized audit logs         |
                     +---------------------------------+
```

---

## 2. Key Components

### 2.1 Celery App (`services/api/infrastructure/queue/celery_app.py`)
- Configured with `task_serializer="json"`, `result_serializer="json"`, and `task_acks_late=True`.
- Helper `register_enqueued_task(task_id, task_name)` stores `task_meta:{task_id}` (TTL 24 hours) upon submission, enabling deterministic HTTP 404 responses for invalid task IDs.

### 2.2 Custom Task Base (`TrackFlowTask` in `custom_task.py`)
- Sets `autoretry_for=(Exception,)`, `max_retries=3`, `retry_backoff=True`, `retry_jitter=True`.
- Late message acknowledgement (`acks_late=True`): message is kept in broker until completion or quarantine.
- `on_failure` hook captures permanently failed tasks and persists a record to the Dead Letter Queue (`dead_letter_queue` table) before message acknowledgement.

### 2.3 Dead Letter Queue & Error Sanitizer (`dlq.py`)
- `sanitize_error_message()`: Strips Bearer tokens (`Bearer ***REDACTED***`), passwords/secrets (`password=***REDACTED***`), and masks emails (`u***@domain.com`).
- `SQLModelDeadLetterQueueAdapter`: Persists failure audit records in SQLite or PostgreSQL.

### 2.4 Status Inspection (`GET /tasks/{task_id}` in `tasks.py`)
- Returns `TaskStatusResponse` with statuses: `pending`, `started`, `success`, or `failure`.
- Unknown IDs return HTTP 404 Not Found.

---

## 3. Operational Guide

### 3.1 Docker Compose Deployment
```bash
# Start full stack including Redis, worker, and Flower
docker compose up -d redis backend worker flower

# Check container health
docker compose ps
```

### 3.2 Flower Monitoring Dashboard
- Access at: [http://localhost:5555](http://localhost:5555)
- Basic Auth: `admin:admin` (configurable via `FLOWER_BASIC_AUTH`)
- Real-time visibility into active workers, queue throughput, task runtime, and failures.

### 3.3 Running Celery Worker Locally
```bash
cd services/api
celery -A infrastructure.queue.celery_app worker -l INFO -c 2
```

