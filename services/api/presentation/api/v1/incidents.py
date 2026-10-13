"""Incidents API router (canonical v1, also mounted at the legacy /api/incidents prefix).

Includes CSV stream analysis and export endpoints formerly defined inline in main.py.
"""

import io
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query as QueryParam, UploadFile
from fastapi.responses import StreamingResponse

from application.incidents.csv_report_service import IncidentCsvReportService
from application.services.incident_service import IncidentService
from domain.common.exceptions import IncidentNotFoundError
from domain.common.ports import CachePort
from domain.schemas.incident_schema import (
    IncidentAnalysisResponse,
    IncidentCreateSchema,
    IncidentResponseSchema,
    IncidentStatusUpdateSchema,
    IncidentSummaryResponse,
)
from presentation.dependencies import (
    get_cache_dep,
    get_incident_csv_report_service_dep,
    get_incident_service_dep,
)

router = APIRouter(tags=["incidents"])

SUMMARY_CACHE_KEY = "incident_summary:global"


@router.post("/analyze", response_model=IncidentAnalysisResponse)
async def analyze_incidents(
    file: UploadFile = File(...),
    report_service: IncidentCsvReportService = Depends(get_incident_csv_report_service_dep),
) -> Any:
    """Analyze an uploaded UTF-8 CSV of incidents and return aggregate metrics."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    try:
        content = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to read uploaded file payload.")

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        text_stream = io.StringIO(content.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid encoding. File must be UTF-8 encoded.")

    try:
        return report_service.analyze(text_stream)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=f"CSV processing failed: {str(ve)}")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred while analyzing the incident data. Please verify file format and try again.",
        )


@router.get("/results/export")
def export_results(
    report_service: IncidentCsvReportService = Depends(get_incident_csv_report_service_dep),
) -> StreamingResponse:
    """Download the latest CSV analysis metrics (404 when nothing was analyzed yet)."""
    csv_text = report_service.export_latest_csv()
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )


@router.get("/summary", response_model=IncidentSummaryResponse)
def get_incident_summary(
    incident_service: IncidentService = Depends(get_incident_service_dep),
    cache: CachePort = Depends(get_cache_dep),
) -> Any:
    """Return aggregated incident metrics grouped by status, category, origin, and branch (TTL cached)."""
    cached = cache.get(SUMMARY_CACHE_KEY)
    if cached is not None:
        return cached

    summary = incident_service.get_summary()
    cache.set(SUMMARY_CACHE_KEY, summary, ttl_seconds=30)
    return summary


@router.get("", response_model=List[IncidentResponseSchema])
def list_incidents(
    status: Optional[str] = QueryParam(None),
    origin: Optional[str] = QueryParam(None),
    branch: Optional[str] = QueryParam(None),
    category: Optional[str] = QueryParam(None),
    incident_service: IncidentService = Depends(get_incident_service_dep),
) -> List[IncidentResponseSchema]:
    """List recorded incidents with optional filters."""
    incidents = incident_service.list_all_incidents(
        status=status, origin=origin, branch=branch, category=category
    )
    return [IncidentResponseSchema(**inc.to_dict()) for inc in incidents]


@router.post("", response_model=IncidentResponseSchema, status_code=201)
def create_incident(
    schema: IncidentCreateSchema,
    incident_service: IncidentService = Depends(get_incident_service_dep),
    cache: CachePort = Depends(get_cache_dep),
) -> IncidentResponseSchema:
    """Create an incident and invalidate the summary cache."""
    created = incident_service.create_incident(schema)
    cache.invalidate_prefix("incident_summary:")
    return IncidentResponseSchema(**created.to_dict())


@router.get("/{incident_id}", response_model=IncidentResponseSchema)
def get_incident_by_id(
    incident_id: str,
    incident_service: IncidentService = Depends(get_incident_service_dep),
) -> IncidentResponseSchema:
    """Return a single incident (404 when missing)."""
    incident = incident_service.get_incident_by_id(incident_id)
    if not incident:
        raise IncidentNotFoundError(f"Incident with ID '{incident_id}' was not found.")
    return IncidentResponseSchema(**incident.to_dict())


@router.patch("/{incident_id}/status", response_model=IncidentResponseSchema)
def update_incident_status(
    incident_id: str,
    schema: IncidentStatusUpdateSchema,
    incident_service: IncidentService = Depends(get_incident_service_dep),
    cache: CachePort = Depends(get_cache_dep),
) -> IncidentResponseSchema:
    """Update an incident's status per lifecycle rules and invalidate the summary cache."""
    updated = incident_service.update_incident_status(incident_id, schema.status)
    cache.invalidate_prefix("incident_summary:")
    return IncidentResponseSchema(**updated.to_dict())
