# Feature Specification: Queue Messages & Async Tasks

**Feature Branch**: `feature/redis-celery-async-queue-task`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "The task is to decouple heavy operations from the API service when an endpoint receives a request that involves long-running work. This task MUST be enqueue and immediately return a task_id to the client. An independent worker shall processes the queue. The client must can check the status of their task at any time. We shall use Redis as a broker in Docker. The API and worker SHALL connect to the same broker. The following endpoint listed MUST be converted into an async task via Celery: POST /reporting/trigger, GET /inventory/products, GET /telemetry/report, POST /incidents/analyze. The endpoints must returns 202 Accepted with a task_id immediately, without waiting for the task to finish. You must create a GET /tasks/{task_id} endpoint that returns current task status (pending, success, failure) and the result when available. If a task fails three times, it moves to a Dead Letter Queue (DLQ) and the failure shall be recorded with task_id, attempt number, and error message. The workers MUST run as separate processes, not inside the FastAPI process. Flower is running and accessible for monitoring the queue during development."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Asynchronous Offloading & Instant Task Acceptance (Priority: P1)

As an API consumer or client application initiating a heavy, resource-intensive operation (such as pipeline triggering, high-volume inventory consolidation, comprehensive telemetry extraction, or deep incident file parsing), I want the system to accept my request asynchronously and immediately return a tracking identifier, so that my HTTP connection is never blocked, starved, or timed out by long-running computations.

**Why this priority**: Directly eliminates thread and worker pool exhaustion in the primary web API, safeguarding API availability and responsiveness under high concurrency.

**Independent Test**: Can be tested independently by submitting an execution request to an offloaded endpoint (e.g., `POST /reporting/trigger` or `POST /incidents/analyze`) with valid parameters. The API immediately acknowledges the request with an HTTP 202 status code and a distinct `task_id` in under 200ms, while the actual heavy workload continues executing in an isolated background process.

**Acceptance Scenarios**:

1. **Given** a valid client request targeting a long-running endpoint (`POST /reporting/trigger`, `GET /inventory/products`, `GET /telemetry/report`, or `POST /incidents/analyze`), **When** the client submits the request, **Then** the API enqueues a lightweight message to the broker and returns an HTTP 202 Accepted response containing a unique `task_id` in less than 200ms without awaiting workload completion.
2. **Given** an uploaded incident file or large query payload, **When** the task is deposited in the queue, **Then** only metadata, resource identifiers, or storage reference paths are stored in the queue message, ensuring large data blobs never bloat broker memory.

---

### User Story 2 - Task Lifecycle Tracking & Result Retrieval (Priority: P2)

As a client application or operator holding a `task_id`, I want to query the status of my asynchronous job at any point in time, so that I can monitor progress (`pending`, `started`, `success`, `failure`) and retrieve the final payload once processing finishes.

**Why this priority**: Essential for asynchronous interactions; clients need a deterministic contract to inspect job lifecycle progression and retrieve completed outcomes.

**Independent Test**: Can be tested independently by querying the task status endpoint (`GET /tasks/{task_id}`) using a valid identifier at various stages (queued, executing, completed, failed) and verifying the state machine transitions and output payload integrity.

**Acceptance Scenarios**:

1. **Given** a recently enqueued task that has not yet been processed by a worker, **When** the client queries `GET /tasks/{task_id}`, **Then** the response indicates status `pending` with empty or null result.
2. **Given** a task currently executing within a worker process, **When** the client queries `GET /tasks/{task_id}`, **Then** the response reflects status `started`.
3. **Given** a successfully executed background task, **When** the client queries `GET /tasks/{task_id}`, **Then** the response returns status `success` along with the complete result payload.
4. **Given** a non-existent or invalid `task_id`, **When** the client queries `GET /tasks/{task_id}`, **Then** the API responds with a descriptive client error (HTTP 404 Not Found) without leaking internal broker details.

---

### User Story 3 - Resilient Retries & Dead Letter Queue Quarantine (Priority: P3)

As a system administrator or reliability engineer, I want transient task failures (e.g., database lock contention, external service blips) to retry automatically with progressive delays, and permanent failures that exceed retry thresholds to be quarantined into a Dead Letter Queue (DLQ), so that failed tasks are not lost and can be audited with full diagnostic context.

**Why this priority**: Guarantees fault tolerance and operational auditability without wedging background worker queues in infinite retry loops.

**Independent Test**: Can be tested independently by simulating a recurring failure in an asynchronous task. Verify that the task retries with increasing backoff intervals up to 3 times, and upon the 3rd failed attempt, stops retrying and logs an entry to the DLQ table containing `task_id`, attempt count, error message, and timestamp.

**Acceptance Scenarios**:

1. **Given** an asynchronous task experiencing a recoverable execution failure, **When** the failure occurs, **Then** the task is rescheduled with an exponential backoff countdown rather than retrying immediately.
2. **Given** an asynchronous task that fails 3 consecutive times, **When** the maximum retry limit is reached, **Then** the task transitions to a failed state, acknowledgement is withheld until failure recording completes, and a Dead Letter Queue record is persisted in the database with `task_id`, attempt number (3), sanitized error message, and timestamp.
3. **Given** a task quarantined in the DLQ, **When** an engineer inspects the database DLQ records, **Then** all diagnostic metadata is present and zero sensitive customer credentials or secrets are leaked in error text.

---

### User Story 4 - Decoupled Worker Execution & Queue Observability (Priority: P4)

As a DevOps engineer or platform developer, I want workers to execute as independent operating system processes separate from the web server and monitor queue metrics in real-time, so that stopping or redeploying the web API does not terminate in-flight processing or discard enqueued messages.

**Why this priority**: Decouples API availability from processing capacity and provides real-time operational visibility into message throughput, latency, and worker health.

**Independent Test**: Can be tested independently by enqueuing tasks, terminating the web API service container/process, and confirming that background workers continue consuming and completing tasks from the broker. Additionally, verify that the monitoring dashboard is accessible on port 5555 and reflects active workers, queued tasks, completed tasks, and failed tasks.

**Acceptance Scenarios**:

1. **Given** queued tasks waiting in the broker, **When** the API service process is stopped or restarted, **Then** the broker retains all queued messages and the background worker processes continue executing without interruption.
2. **Given** active workers running in development, **When** opening the monitoring web interface (Flower on port 5555), **Then** real-time metrics showing connected workers, queue backlogs, active tasks, completed tasks, and failed executions are displayed.

---

### Edge Cases

- **Broker Outage or Connection Loss**: How does the API respond when the message broker is unreachable? The API MUST catch connection timeouts gracefully, log an alert, and return an HTTP 503 Service Unavailable or sanitized HTTP 500 error instead of hanging or crashing the web process.
- **Worker Crash During Task Execution**: What happens if a worker process crashes or is killed while executing a task? The broker MUST detect worker disconnection, and unacknowledged messages MUST be redelivered according to visibility timeout rules.
- **Runaway / Hung Tasks**: What prevents a task from hanging indefinitely and starving the worker concurrency pool? Every task MUST have an enforced maximum execution timeout (time limit). Tasks exceeding this limit are terminated and marked as failed.
- **Malformed Input Payloads**: What happens if the request payload fails validation prior to queuing? The API MUST validate parameters synchronously (e.g., via Pydantic request models) and return HTTP 400/422 immediately before any message is dispatched to the queue.
- **Large Payload Ingestion**: For endpoints like `/incidents/analyze` receiving multipart file uploads, files MUST NOT be dumped raw into the broker. The file content MUST be saved to a shared/temporary staging path or database reference, passing only the file path/identifier into the queue message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an asynchronous task broker and worker infrastructure running independently from the main web application process.
- **FR-002**: System MUST convert the following resource-heavy operations into asynchronous background tasks returning an immediate HTTP 202 Accepted response with a unique `task_id`:
  - `POST /reporting/trigger` (orchestration / ETL execution)
  - `GET /inventory/products` (heavy database I/O / stock calculation)
  - `GET /telemetry/report` (event extraction & pandas processing)
  - `POST /incidents/analyze` (incident file parsing & memory-intensive processing)
- **FR-003**: System MUST provide a task inspection endpoint `GET /tasks/{task_id}` that returns the current lifecycle status (`pending`, `started`, `success`, `failure`) and the computed result payload when available.
- **FR-004**: System MUST keep queue messages lightweight by passing only identifiers, query parameters, or file storage paths rather than raw binary data or large datasets.
- **FR-005**: System MUST enforce an acknowledgment policy where messages are acknowledged (`ACK`) only upon successful completion or upon final handoff to the Dead Letter Queue.
- **FR-006**: System MUST enforce a maximum execution duration (timeout) for every asynchronous background task.
- **FR-007**: System MUST automatically retry failed tasks up to a maximum of 3 attempts with exponential backoff between attempts.
- **FR-008**: System MUST persist a Dead Letter Queue (DLQ) record into the relational database when a task exhausts all 3 retry attempts, recording `task_id`, `attempt_number`, `error_message`, and `created_at` timestamp.
- **FR-009**: System MUST record structured logs for every task execution event including `task_id`, retry attempt index, execution duration, and resulting status (with sanitized error text on failure).
- **FR-010**: System MUST provide a web-based queue and worker monitoring interface (Flower) accessible during development on port 5555.
- **FR-011**: System MUST read broker connection configurations from environment variables (`REDIS_URL`) across both the web API and worker environments.
- **FR-012**: System MUST ensure stopping or restarting the web API process does not terminate worker processes or cause message loss in the broker.
- **FR-013**: System MUST adhere to Monorepo Constitution Principle I and II, declaring explicit Pydantic response models for all new and modified endpoints, ensuring zero raw traceback leakage.

### Key Entities *(include if feature involves data)*

- **Task Message Envelope**: Represents the unit of work queued in the broker. Contains `task_id`, task name, arguments (references/IDs only), execution countdown/retry metadata, and routing queue.
- **Task Status Descriptor**: Represents the queryable state of an execution in the result store. Contains `task_id`, state (`pending`, `started`, `success`, `failure`), `result` (nullable JSON object), and timestamps.
- **Dead Letter Queue (DLQ) Record**: Represents a persistently stored record of an unrecoverable task failure. Contains `id` (primary key), `task_id` (string reference), `task_name` (string), `attempt_number` (integer), `error_message` (sanitized text), and `failed_at` (UTC timestamp).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Offloaded API endpoints return an HTTP 202 Accepted acknowledgment with `task_id` in under 200 milliseconds, independent of background workload duration.
- **SC-002**: Web API process maintains zero thread starvation or request timeout errors during concurrent executions of heavy background operations.
- **SC-003**: 100% of tasks exceeding the maximum retry limit (3 attempts) are quarantined in the Dead Letter Queue database with complete diagnostic metadata.
- **SC-004**: Task status inspection endpoint (`GET /tasks/{task_id}`) reliably reports state transitions (`pending` -> `started` -> `success` / `failure`) with accurate result delivery upon completion.
- **SC-005**: The monitoring dashboard is accessible on port 5555 and accurately reflects active worker counts, message throughput, and task statuses during validation tests.
- **SC-006**: Stopping the web API container/process produces zero lost messages in the queue broker and zero interruptions to actively processing background workers.

## Assumptions

- Redis is configured with the official Docker image using the `noeviction` memory policy on port 6379 to guarantee that queued messages are never silently evicted due to memory pressure.
- For GET endpoints offloaded to async tasks (`/inventory/products`, `/telemetry/report`), the endpoint returns an HTTP 202 Accepted status with a `task_id`, allowing clients to poll `GET /tasks/{task_id}` for the final dataset.
- Large incident CSV files submitted to `/incidents/analyze` are stored temporarily on disk or shared staging volume, and the file path reference is passed to the queue message.
- The DLQ storage table uses the existing application relational database (`inventory.db` or primary application database adapter) to maintain centralized persistence and ACID guarantees.
- Celery worker concurrency pool configuration and task timeouts will be tailored to standard development and container environment capacities.

