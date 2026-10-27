"""Domain Pydantic DTO models matching reporting-api.yaml contract."""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Sanitized API error response."""

    detail: str = Field(description="Sanitized error description.")


class PipelineExecutionLogDTO(BaseModel):
    """Execution state and audit metadata for a pipeline run."""

    model_config = ConfigDict(from_attributes=True)

    run_id: UUID = Field(description="Unique execution identifier.")
    flow_name: str = Field(description="Name of the executed pipeline flow.")
    started_at: datetime = Field(description="UTC execution start time.")
    ended_at: Optional[datetime] = Field(default=None, description="UTC execution completion time.")
    records_processed: int = Field(default=0, description="Number of raw source records processed.")
    status: Literal["RUNNING", "SUCCESS", "FAILED"] = Field(description="Execution state.")
    error_details: Optional[str] = Field(default=None, description="Sanitized failure details.")


class PipelineStatusResponse(BaseModel):
    """Operational health and status of the latest pipeline execution."""

    latest_run: Optional[PipelineExecutionLogDTO] = Field(
        default=None,
        description="Metadata of the most recent pipeline execution.",
    )
    is_running: bool = Field(description="True if an execution is currently active.")
    healthy: bool = Field(description="True if latest run completed successfully without errors.")


class PipelineTriggerRequest(BaseModel):
    """Optional parameters for ad-hoc or backfill pipeline execution."""

    period_start: Optional[datetime] = Field(
        default=None,
        description="Optional window start date in UTC.",
    )
    period_end: Optional[datetime] = Field(
        default=None,
        description="Optional window end date in UTC.",
    )


class PipelineTriggerResponse(BaseModel):
    """Response confirming accepted pipeline execution trigger."""

    run_id: UUID = Field(description="Unique execution run identifier.")
    status: Literal["INITIATED", "QUEUED"] = Field(description="Execution acceptance state.")
    message: str = Field(description="Status message regarding execution launch.")


class ExecutiveKpiSnapshotDTO(BaseModel):
    """Pre-computed weekly business performance snapshot for executive dashboards."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: UUID = Field(description="Unique snapshot identifier.")
    period_start: datetime = Field(description="Start of reporting window in ISO 8601 UTC.")
    period_end: datetime = Field(description="End of reporting window in ISO 8601 UTC.")
    country: Literal["US", "ES", "GLOBAL"] = Field(description="Geographic scope.")
    shipments_volume: int = Field(ge=0, description="Total outbound packages fulfilled.")
    on_time_delivery_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Ratio of deliveries completed within SLA transit windows.",
    )
    operational_cost_eur: float = Field(
        ge=0.0,
        description="Total fulfillment and logistics cost in Euros.",
    )
    returns_rate: float = Field(
        ge=0.0,
        le=100.0,
        description="Returned packages as a percentage of total shipments.",
    )
    customer_satisfaction_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Composite satisfaction score (0-100).",
    )
    generated_at: datetime = Field(description="Timestamp when snapshot was persisted.")


# Alias for contract compatibility
ExecutiveKpiSnapshot = ExecutiveKpiSnapshotDTO


class ExecutiveKpisResponse(BaseModel):
    """List of pre-computed weekly executive KPI snapshots."""

    count: int = Field(description="Number of returned snapshots.")
    snapshots: List[ExecutiveKpiSnapshotDTO] = Field(
        description="List of snapshot records.",
    )


__all__ = [
    "ErrorResponse",
    "ExecutiveKpiSnapshot",
    "ExecutiveKpiSnapshotDTO",
    "ExecutiveKpisResponse",
    "PipelineExecutionLogDTO",
    "PipelineStatusResponse",
    "PipelineTriggerRequest",
    "PipelineTriggerResponse",
]
