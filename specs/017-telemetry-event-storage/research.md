# Phase 0: Research & Technical Decisions - Telemetry Event Storage

**Feature**: `017-telemetry-event-storage`  
**Date**: 2026-10-15  
**Status**: Completed  

---

## 1. Batch Request Ingestion Strategy & Partial Validation

### Context & Problem
FastAPI and Pydantic v2 typically enforce strict schema validation at the HTTP boundary. If an endpoint defines `batch: TelemetryBatch` where `events: List[TelemetryEvent]`, a single malformed item in the array causes Pydantic to raise a `RequestValidationError`, aborting the entire request and returning HTTP 422 Unprocessable Entity.

However, Feature Specification `017-telemetry-event-storage` (FR-002, FR-004, FR-006) requires:
- The outer envelope must validate that an `events` array exists. Missing or non-list payloads must be rejected with HTTP 422 (e.g., `{}` or `{"events": "invalid"}`).
- Valid events in a batch must NOT be dropped due to adjacent malformed events.
- Each event must be evaluated individually. Valid events are accepted; invalid ones are isolated and counted as `rejected`.
- The endpoint must return HTTP 200 OK with `{ "received": N, "stored": M, "rejected": R }`.
- Empty batches (`{"events": []}`) must be processed gracefully and return `{ "received": 0, "stored": 0, "rejected": 0 }` with HTTP 200 OK.

### Decision
Define a two-tier validation approach:
1. **Outer Request DTO (`RawTelemetryBatch`)**:
   ```python
   class RawTelemetryBatch(BaseModel):
       model_config = ConfigDict(extra="forbid")
       events: List[Dict[str, Any]] = Field(
           ...,
           description="Array of raw event objects for individual envelope validation."
       )
   ```
   If a client provides `{}` or `{"events": "bad"}` or extra envelope fields, FastAPI rejects the request with HTTP 422 immediately.
   If a client provides `{"events": []}`, Pydantic accepts it, and the service evaluates `0` events.
2. **Per-Item Validation in Application/Domain Layer**:
   The service iterates through `raw_batch.events`. For each item:
   ```python
   try:
       valid_event = TelemetryEvent.model_validate(raw_item)
       valid_events.append(valid_event)
   except ValidationError as err:
       rejected_count += 1
       logger.warning("Telemetry event rejected: index=%d error=%s", idx, str(err))
   ```
   All valid events are passed to the persistent sink adapter for bulk insertion.

### Rationale
- Strictly preserves HTTP-level contract requirements for the batch envelope.
- Guarantees complete fault tolerance: malformed events never abort valid telemetry ingestion.
- Eliminates overhead of custom middleware or raw ASGI stream parsing while maintaining clean Pydantic integration.

### Alternatives Considered
- *Custom Request Validator Middleware*: Intercepts raw JSON stream before routing. Rejected because it bypasses FastAPI router annotations, hides error types from OpenAPI docs, and violates Principle I (Service Boundaries).
- *Union Types in Pydantic (`List[Union[TelemetryEvent, Any]]`)*: Causes confusing coercion behavior and generates opaque OpenAPI schemas.
- *Strict All-or-Nothing Validation*: Rejected because it directly violates FR-004 and causes telemetry data loss in high-throughput distributed clients.

---

## 2. Database Persistence & Storage Schema with Cross-Dialect JSON Support

### Context & Problem
The system utilizes Supabase / PostgreSQL in production, with automatic fallback to SQLite (`inventory.db`) during isolated testing or when cloud database connectivity is unavailable (via `SQLModelClientManager`).
The `telemetry_events` table must record standard event attributes:
- `event_id` (UUIDv4 primary key)
- `timestamp` (UTC datetime)
- `session_id` (string, indexed)
- `user_id` (optional string, indexed)
- `event_type` (snake_case string, indexed)
- `schema_version` (semantic version string)
- `request_id` (string, indexed)
- `properties` (arbitrary structured JSON dictionary)
- `created_at` (audit timestamp default to UTC now)

The schema must work seamlessly across both PostgreSQL (JSON / JSONB column) and SQLite (JSON / text column) without dialect-specific driver crashes.

### Decision
Create the ORM table model `TelemetryEventRecord(SQLModel, table=True)` in `services/api/infrastructure/persistence/sqlmodel/models.py`:
```python
from uuid import UUID
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON

class TelemetryEventRecord(SQLModel, table=True):
    __tablename__ = "telemetry_events"

    event_id: UUID = Field(primary_key=True, index=True, nullable=False)
    timestamp: datetime = Field(index=True, nullable=False)
    session_id: str = Field(index=True, nullable=False)
    user_id: Optional[str] = Field(default=None, index=True, nullable=True)
    event_type: str = Field(index=True, nullable=False)
    schema_version: str = Field(nullable=False)
    request_id: str = Field(index=True, nullable=False)
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )
```
For persistence, execute bulk insertion using SQLModel / SQLAlchemy session operations within an explicit transaction:
```python
def record_events(self, events: List[TelemetryEvent]) -> int:
    if not events:
        return 0
    records = [
        TelemetryEventRecord(
            event_id=e.eventId,
            timestamp=e.timestamp,
            session_id=e.sessionId,
            user_id=e.userId,
            event_type=e.event_type,
            schema_version=e.schemaVersion,
            request_id=e.requestId,
            properties=e.properties,
        )
        for e in events
    ]
    with self._get_session() as session:
        session.add_all(records)
        session.commit()
        return len(records)
```

### Rationale
- `sa_column=Column(JSON)` is standard SQLAlchemy that automatically compiles to native `JSON` / `JSONB` in PostgreSQL and transparent text/JSON in SQLite.
- `session.add_all()` within an atomic transaction guarantees single-trip bulk insert efficiency while preserving transaction rollback semantics if the database fails.
- Maps directly to the existing `SQLModelClientManager` singleton and `init_db()` auto-migration flow.

### Alternatives Considered
- *Separate Raw SQL with `COPY` or `INSERT ... VALUES (...), (...)`*: Highly database-dialect dependent (syntax varies between SQLite and Postgres) and complicates unit testing with in-memory SQLite.
- *Separate Document Store (MongoDB / TinyDB)*: Violates Constitution Database Isolation rules and monorepo architectural standards. Relational storage in Supabase / SQLModel is the ratified standard.

---

## 3. Hexagonal Architecture Port and Service Layer Evolution

### Context & Problem
Currently, `domain.telemetry.ports.TelemetrySinkPort` defines:
```python
class TelemetrySinkPort(ABC):
    @abstractmethod
    def record_event(self, event: TelemetryEvent) -> None: ...
    @abstractmethod
    def record_batch(self, batch: TelemetryBatch) -> int: ...
```
And `LoggingTelemetrySink` is the only existing sink adapter.
To support partial validation and persistent storage:
1. The domain port should cleanly accept a list of validated `TelemetryEvent` instances to persist in bulk: `record_events(self, events: List[TelemetryEvent]) -> int`.
2. The driven adapter `SQLModelTelemetrySink` will implement `TelemetrySinkPort` and persist records via SQLModel sessions.
3. The existing `LoggingTelemetrySink` can also be maintained for fallback/logging.
4. `TelemetryService` will orchestrate the validation of raw batches, dispatch valid events to `sink.record_events(valid_events)`, and construct the complete `IngestReceipt(received=..., stored=..., rejected=...)`.
5. `IngestReceipt` in `domain/telemetry/models.py` must be extended with `stored: int` and `rejected: int` with backward-compatible defaults or explicit assignments.

### Decision
1. Update `domain.telemetry.models.IngestReceipt`:
   ```python
   class IngestReceipt(BaseModel):
       received: int = Field(..., ge=0, description="Total events evaluated.")
       stored: int = Field(default=0, ge=0, description="Events successfully persisted.")
       rejected: int = Field(default=0, ge=0, description="Events failing schema validation.")
   ```
2. Update `TelemetrySinkPort`:
   ```python
   class TelemetrySinkPort(ABC):
       @abstractmethod
       def record_events(self, events: List[TelemetryEvent]) -> int:
           """Persist a list of validated telemetry events in a single transaction."""
           ...
   ```
3. Implement `SQLModelTelemetrySink` in `services/api/infrastructure/persistence/sqlmodel/telemetry_sink.py`:
   - Connects through `sqlmodel_manager`.
   - Executes atomic bulk insert of `TelemetryEventRecord`.
4. Update `services/api/presentation/dependencies.py`:
   - Wire `SQLModelTelemetrySink` as the default driven adapter for `TelemetryService`:
   ```python
   def get_telemetry_service_dep(
       session: Session = Depends(get_db),
   ) -> TelemetryService:
       sink = SQLModelTelemetrySink(session=session)
       return TelemetryService(sink=sink)
   ```

### Rationale
- Maintains clean Hexagonal Architecture: domain layer defines ports, infrastructure provides SQLModel implementation, presentation binds dependencies.
- Swappable sinks enable zero-side-effect unit testing with in-memory mocks.

### Alternatives Considered
- *Direct Database Access in Route Handler*: Violates Principle I (Service Boundaries) and Constitution Section "Database & Persistence Isolation".

---

## 4. Immutability and Transaction Isolation Guarantees

### Context & Problem
Requirement FR-008 states: "The underlying storage table (`telemetry_events`) MUST be write-only and immutable, preventing updates or row modifications after persistence."

### Decision
1. Application Layer: The `TelemetrySinkPort` and `SQLModelTelemetrySink` expose ONLY append methods (`record_events`). No update, put, patch, or delete methods exist in the interface or service.
2. Presentation Layer: No API routes exist or will be created for mutating or deleting stored telemetry events.
3. Database DDL: The table contains only `event_id` primary key and append timestamps. In PostgreSQL / Supabase production migrations, table-level grants can restrict operational roles to `INSERT, SELECT` while omitting `UPDATE, DELETE`.

### Rationale
Enforces write-only immutability by construction across application, API, and repository boundaries.

---

## 5. Backward Compatibility with Frontend and Existing Tests

### Context & Problem
- Frontend client (`uis/backoffice/app/services/telemetry.ts`) sends `POST /telemetry/events` with `{ "events": [...] }`.
- Frontend expects HTTP 200 OK to consider the batch delivered. If HTTP 422 or 500 is returned, it triggers exponential backoff retry loops.
- Existing tests check `response.status_code == 200` and `data["received"] == 2`.
- Requirement FR-007 requires 100% backward compatibility.

### Decision
- The response model `IngestReceipt` keeps `received` as its primary field and adds `stored` and `rejected`.
- Mixed batches and all-rejected batches return HTTP 200 OK with `received`, `stored`, `rejected` counts, satisfying the invariant `received = stored + rejected`.
- Requests with invalid envelope format (e.g. missing `events` array or non-list) continue to return HTTP 422, preserving standard HTTP API semantics for unprocessable request bodies.
- Endpoint alias `/api/v1/telemetry/events` remains active with identical behavior.
