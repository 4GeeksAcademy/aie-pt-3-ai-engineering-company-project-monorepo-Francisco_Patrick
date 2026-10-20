"""Contract: Callable Python Interface between services/reporting and data/pipelines.

Defines the explicit boundary protocol ensuring no ETL logic leaks into API controllers,
and guaranteeing type safety and contract encapsulation.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Protocol, Tuple
from uuid import UUID
from pydantic import BaseModel, Field


class PipelineStatusEnum(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class GeographicScopeEnum(str, Enum):
    US = "US"
    ES = "ES"
    GLOBAL = "GLOBAL"


class PipelineExecutionLogModel(BaseModel):
    """Pydantic model for pipeline execution audit log."""
    run_id: UUID
    flow_name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    records_processed: int = 0
    status: PipelineStatusEnum
    error_details: Optional[str] = None


class PipelineStatusModel(BaseModel):
    """Pipeline health and latest execution response."""
    latest_run: Optional[PipelineExecutionLogModel] = None
    is_running: bool = False
    healthy: bool = True


class ExecutiveKpiSnapshotModel(BaseModel):
    """Aggregated business performance snapshot."""
    snapshot_id: UUID
    period_start: datetime
    period_end: datetime
    country: GeographicScopeEnum
    shipments_volume: int = Field(ge=0)
    on_time_delivery_rate: float = Field(ge=0.0, le=1.0)
    operational_cost_eur: float = Field(ge=0.0)
    returns_rate: float = Field(ge=0.0, le=100.0)
    customer_satisfaction_score: float = Field(ge=0.0, le=100.0)
    generated_at: datetime


class PipelineTriggerResponseModel(BaseModel):
    """Response returned upon triggering a pipeline execution."""
    run_id: UUID
    status: str
    message: str


class PipelineInterfaceProtocol(Protocol):
    """Protocol defining callable operations exposed by data/pipelines/."""

    def get_pipeline_status(self) -> PipelineStatusModel:
        """Query the latest execution log and determine operational status.
        
        Returns:
            PipelineStatusModel detailing health and latest execution state.
        """
        ...

    def trigger_pipeline_run(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> PipelineTriggerResponseModel:
        """Trigger an ad-hoc or backfill pipeline execution run.
        
        Args:
            start_date: Optional boundary start datetime.
            end_date: Optional boundary end datetime.
            
        Returns:
            PipelineTriggerResponseModel with initiated run ID.
            
        Raises:
            PipelineConflictError: If a pipeline run is already actively running.
            ValueError: If start_date > end_date.
        """
        ...

    def get_executive_kpis(
        self,
        country: Optional[str] = "GLOBAL",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[int, List[ExecutiveKpiSnapshotModel]]:
        """Retrieve executive KPI snapshots matching criteria.
        
        Args:
            country: Regional scope ('US', 'ES', 'GLOBAL').
            start_date: Optional start boundary.
            end_date: Optional end boundary.
            
        Returns:
            Tuple of (total_count, list_of_snapshots).
        """
        ...
