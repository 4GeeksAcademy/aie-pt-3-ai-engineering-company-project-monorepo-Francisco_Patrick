"""Presentation route handlers for executive reporting API.

Adheres strictly to Monorepo Constitution Principle I and II:
- Declares explicit Pydantic response models and typed parameters.
- Contains zero inline ETL or direct ORM leakage.
- Delegates 100% of pipeline operations to data.pipelines.reporting_interface.
"""

from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from data.pipelines.reporting_interface import (
    PipelineActiveConflictError,
    get_executive_kpis,
    get_pipeline_status,
    trigger_pipeline_run,
)
from services.reporting.domain.schemas import (
    ErrorResponse,
    ExecutiveKpisResponse,
    PipelineStatusResponse,
    PipelineTriggerRequest,
    PipelineTriggerResponse,
)

logger = logging.getLogger("services.reporting.presentation.routes")

router = APIRouter(tags=["Reporting"])


@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    responses={
        status.HTTP_200_OK: {"model": PipelineStatusResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
    summary="Get Pipeline Health & Execution Status",
    description="Returns the execution status of the most recent business performance pipeline run.",
)
def read_pipeline_status() -> PipelineStatusResponse:
    """Retrieve operational status and health of the latest pipeline execution."""
    try:
        data = get_pipeline_status()
        return PipelineStatusResponse.model_validate(data)
    except Exception as exc:
        logger.error("Failed to retrieve pipeline status: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving pipeline status.",
        )


@router.post(
    "/trigger",
    response_model=PipelineTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_202_ACCEPTED: {"model": PipelineTriggerResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
    summary="Manually Trigger Pipeline Execution",
    description="Initiates an ad-hoc or backfill execution of the business performance pipeline.",
)
def trigger_pipeline(
    payload: Optional[PipelineTriggerRequest] = None,
) -> PipelineTriggerResponse:
    """Trigger a new pipeline execution run."""
    period_start = payload.period_start if payload else None
    period_end = payload.period_end if payload else None

    try:
        result = trigger_pipeline_run(period_start=period_start, period_end=period_end)
        return PipelineTriggerResponse.model_validate(result)
    except PipelineActiveConflictError as conflict_err:
        logger.warning("Pipeline trigger rejected due to active conflict: %s", conflict_err)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(conflict_err),
        )
    except Exception as exc:
        logger.error("Unexpected error triggering pipeline: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while initiating the pipeline execution.",
        )


@router.get(
    "/kpis",
    response_model=ExecutiveKpisResponse,
    responses={
        status.HTTP_200_OK: {"model": ExecutiveKpisResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
    summary="Query Executive KPI Snapshots",
    description="Retrieves weekly business performance snapshots for executive dashboards.",
)
def read_executive_kpis(
    country: Optional[str] = Query(
        default="GLOBAL",
        pattern="^(US|ES|GLOBAL)$",
        description="Filter by geographic scope: US, ES, or GLOBAL.",
    ),
    start_date: Optional[datetime] = Query(
        default=None,
        description="Start of reporting window in ISO 8601 UTC format.",
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="End of reporting window in ISO 8601 UTC format.",
    ),
) -> ExecutiveKpisResponse:
    """Retrieve pre-aggregated executive KPI snapshots filtered by country and date."""
    try:
        result = get_executive_kpis(
            country=country,
            start_date=start_date,
            end_date=end_date,
        )
        return ExecutiveKpisResponse.model_validate(result)
    except Exception as exc:
        logger.error("Failed to query executive KPIs: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving executive KPI snapshots.",
        )
