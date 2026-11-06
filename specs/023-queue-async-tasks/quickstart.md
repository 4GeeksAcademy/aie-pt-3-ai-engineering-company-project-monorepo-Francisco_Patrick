# Quickstart Validation Guide: Queue Messages & Async Tasks

This guide provides end-to-end runnable scenarios to validate asynchronous task offloading, status tracking, retry handling, Dead Letter Queue (DLQ) quarantining, and worker decoupling using Redis and Celery.

---

## 1. Prerequisites & Environment Setup

### 1.1 Start Infrastructure Containers (Redis + Worker + Flower)
Ensure Docker is running and spin up the Redis broker, background Celery worker, and Flower monitoring interface:

```bash
# Start redis, backend, worker, and flower in background
docker compose up -d redis backend worker flower

# Check that containers are healthy
docker compose ps
```

Verify that:
- Redis is listening on port `6379`.
- Flower dashboard is accessible at [http://localhost:5555](http://localhost:5555).
- Web API is responding at [http://localhost:8000/docs](http://localhost:8000/docs).

### 1.2 Local Development Mode (Without Full Docker)
If running directly on the host machine:

```bash
# Terminal 1: Start Redis container
docker run -d --name trackflow-redis -p 6379:6379 redis:7-alpine redis-server --appendonly yes --maxmemory-policy noeviction

# Terminal 2: Start background worker
cd services/api
celery -A infrastructure.queue.celery_app worker -l INFO -c 2

# Terminal 3: Start Flower dashboard
cd services/api
celery -A infrastructure.queue.celery_app flower --port=5555

# Terminal 4: Start FastAPI server
cd services/api
uvicorn main:app --reload --port 8000
```

---

## 2. Validation Scenarios

### Scenario 1: Asynchronous Offloading & Instant 202 Acceptance
**Goal**: Verify that heavy endpoints return HTTP 202 with `task_id` in under 200ms without blocking.

#### Step 1: Submit Heavy Request
```bash
curl -i -X POST http://localhost:8000/api/v1/reporting/trigger \
  -H "Content-Type: application/json" \
  -d '{"period_start": "2026-10-01T00:00:00Z", "period_end": "2026-10-31T23:59:59Z"}'
```

#### Expected Outcome:
- HTTP Status: `202 Accepted`
- Response time: `< 200ms`
- Response Body:
  ```json
  {
    "task_id": "<UUID>",
    "status": "pending",
    "message": "Reporting pipeline execution enqueued.",
    "poll_url": "/api/v1/tasks/<UUID>",
    "created_at": "..."
  }
  ```

---

### Scenario 2: Task Lifecycle Tracking & Result Retrieval
**Goal**: Verify that `GET /tasks/{task_id}` accurately transitions from `pending` -> `started` -> `success` with valid results.

#### Step 1: Query Task Status Immediately
```bash
curl -i http://localhost:8000/api/v1/tasks/<UUID_FROM_SCENARIO_1>
```

#### Expected Outcome:
- HTTP Status: `200 OK`
- Status is `"pending"` or `"started"`.
- Result is `null`.

#### Step 2: Poll Until Completed
Wait 2–5 seconds and re-query:
```bash
curl -i http://localhost:8000/api/v1/tasks/<UUID_FROM_SCENARIO_1>
```

#### Expected Outcome:
- HTTP Status: `200 OK`
- Status is `"success"`.
- `result` contains the completed pipeline or aggregation payload.
- `completed_at` is populated.

---

### Scenario 3: Non-Existent Task 404 Verification
**Goal**: Verify that querying an unsubmitted UUID returns a clean 404 rather than hung or ghost `pending`.

#### Step 1: Query Fabricated UUID
```bash
curl -i http://localhost:8000/api/v1/tasks/00000000-0000-0000-0000-000000000000
```

#### Expected Outcome:
- HTTP Status: `404 Not Found`
- Response Body:
  ```json
  {
    "detail": "Task '00000000-0000-0000-0000-000000000000' not found."
  }
  ```

---

### Scenario 4: Retries & Dead Letter Queue (DLQ) Quarantine
**Goal**: Verify that a failing task retries 3 times with exponential backoff and then commits an audit entry to `dead_letter_queue`.

#### Step 1: Trigger Failing Task Simulation
Run integration test simulating task failure:
```bash
pytest services/api/tests/test_celery_dlq.py -v
```

#### Step 2: Inspect Database DLQ Table
Query the SQLite database:
```bash
sqlite3 services/api/inventory.db "SELECT id, task_id, task_name, attempt_number, error_message, failed_at FROM dead_letter_queue ORDER BY id DESC LIMIT 1;"
```

#### Expected Outcome:
- `attempt_number`: `3`
- `error_message`: Sanitized error text (no leaked credentials or tokens).
- `failed_at`: Valid UTC timestamp.

---

### Scenario 5: Web API Decoupling from Background Worker
**Goal**: Verify that in-flight and queued jobs survive web server shutdown.

#### Step 1: Enqueue Tasks & Stop Web Container
```bash
# Enqueue task
TASK_ID=$(curl -s -X POST http://localhost:8000/api/v1/inventory/products | jq -r .task_id)

# Immediately restart or stop the web backend service
docker compose stop backend

# Check worker logs to confirm worker is still processing the job
docker compose logs worker --tail=20
```

#### Step 2: Restart Web API & Retrieve Result
```bash
docker compose start backend
sleep 2
curl -s http://localhost:8000/api/v1/tasks/$TASK_ID | jq .
```

#### Expected Outcome:
- Task completed successfully with status `"success"`.
- Zero messages lost or corrupted.

---

### Scenario 6: Observability with Flower
**Goal**: Verify queue monitoring dashboard functionality.

1. Open browser at [http://localhost:5555](http://localhost:5555).
2. View the **Dashboard** tab: confirm connected worker count `>= 1`.
3. View the **Tasks** tab: confirm that the tasks executed above are listed with their state, runtime duration, and arguments.

