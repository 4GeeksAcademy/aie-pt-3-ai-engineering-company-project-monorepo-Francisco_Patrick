# Python Interface Contract: Pipeline Subflows Architecture

**Feature Branch**: `feature/021-pipeline-subflows-and-tests`  
**Date**: 2026-10-27  
**Module**: `data/pipelines/pipeline.py`  

---

## 1. Overview

This contract formalizes the Python function signatures, execution decorators, argument schemas, return types, and error behaviors for the modular subflows and parent orchestrator flow.

In compliance with **FR-001, FR-002, and FR-003**:
- All subflows are decorated with `@flow`.
- Subflows communicate strictly through explicit arguments and return values.
- Shared mutable global variables are strictly prohibited.
- All names reflect TrackFlow business domain vocabulary.

---

## 2. Subflow Interface Definitions

### 2.1 Extraction Subflow

```python
@flow(
    name="extract_fulfillment_and_telemetry_flow",
    description="Extracts raw domain telemetry and operational fulfillment events within watermark bounds.",
    retries=2,
    retry_delay_seconds=15,
)
def extract_fulfillment_and_telemetry_flow(
    period_start: datetime,
    period_end: datetime,
) -> Dict[str, pd.DataFrame]:
    """Execute raw extraction of orders, tracking, returns, and CX events.

    Args:
        period_start: Inclusive ISO UTC start timestamp of the reporting window.
        period_end: Inclusive ISO UTC end timestamp of the reporting window.

    Returns:
        Dictionary mapping entity strings ('orders', 'tracking', 'returns', 'cx')
        to strongly typed pandas DataFrames. Never returns None; returns empty DataFrames
        with valid columns when no records exist.

    Raises:
        DatabaseConnectionError / OperationalError: On persistent database failure after retries.
    """
```

---

### 2.2 Transformation Subflow

```python
@flow(
    name="transform_executive_performance_kpis_flow",
    description="Transforms raw operational event DataFrames into regional and global KPI snapshots.",
)
def transform_executive_performance_kpis_flow(
    raw_data: Dict[str, pd.DataFrame],
    period_start: datetime,
    period_end: datetime,
) -> List[Dict[str, Any]]:
    """Transform extracted data into pre-aggregated executive KPI snapshots.

    Args:
        raw_data: Dictionary mapping entity strings to extracted pandas DataFrames.
        period_start: Beginning boundary of the reporting window.
        period_end: Ending boundary of the reporting window.

    Returns:
        List of three snapshot dictionaries representing 'US', 'ES', and 'GLOBAL' scopes.
        Each snapshot dictionary conforms strictly to the ExecutiveKpiSnapshot schema.

    Notes:
        Applies defensive zero-division guardrails and neutral fallbacks for empty datasets.
    """
```

---

### 2.3 Load Subflow

```python
@flow(
    name="load_executive_kpi_snapshots_flow",
    description="Persists transformed KPI snapshot records into the reporting database via idempotent upsert.",
    retries=3,
    retry_delay_seconds=10,
)
def load_executive_kpi_snapshots_flow(
    snapshots: List[Dict[str, Any]],
    run_id: UUID,
) -> int:
    """Atomically upsert pre-computed KPI snapshots into executive_kpi_snapshots.

    Args:
        snapshots: List of validated snapshot dictionaries.
        run_id: Unique pipeline execution run identifier.

    Returns:
        Integer count of snapshot records successfully persisted (typically 3).

    Raises:
        SQLAlchemyError: On transaction or constraint failure.
    """
```

---

### 2.4 Auxiliary Notification Subflow

```python
@flow(
    name="dispatch_pipeline_notifications_flow",
    description="Non-critical auxiliary subflow dispatching execution webhook notifications.",
)
def dispatch_pipeline_notifications_flow(
    run_id: UUID,
    status: str,
    summary: Dict[str, Any],
) -> bool:
    """Publish pipeline execution completion alerts.

    Args:
        run_id: Unique execution identifier.
        status: Execution status ('SUCCESS' | 'FAILED').
        summary: Dictionary containing execution metrics (records_processed, duration).

    Returns:
        Boolean indicating dispatch success.
    """
```

---

## 3. Master Orchestrator Flow

```python
@flow(
    name="executive_performance_pipeline_flow",
    description="Overarching master flow coordinating extraction, transformation, load, and audit logging.",
)
def executive_performance_pipeline_flow(
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Coordinate the complete executive performance telemetry pipeline.

    Execution Sequence:
        1. Resolve reporting window (default: preceding Monday 00:00:00 to Sunday 23:59:59 UTC).
        2. Create audit log entry with status 'RUNNING' in pipeline_execution_logs.
        3. Invoke extract_fulfillment_and_telemetry_flow(actual_start, actual_end).
        4. Invoke transform_executive_performance_kpis_flow(raw_data, actual_start, actual_end).
        5. Invoke load_executive_kpi_snapshots_flow(snapshots, run_id).
        6. Invoke dispatch_pipeline_notifications_flow(...) with return_state=True.
           - Log warning if auxiliary dispatch fails; do not abort execution.
        7. Update audit log entry with status 'SUCCESS' and records_processed count.
        8. Return persisted snapshot records.

    Error Handling:
        - Catches exceptions, sanitizes error messages, updates audit log with status 'FAILED',
          and re-raises exception.
    """
```
