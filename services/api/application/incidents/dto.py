"""Incident and stream analysis application Data Transfer Objects (DTOs)."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class IncidentCreateDTO(BaseModel):
    """Payload for creating a new operational incident."""

    title: str = Field(..., min_length=1, max_length=200, description="Incident title")
    description: str = Field(..., min_length=1, description="Detailed problem description")
    category: str = Field(..., description="Operational category")
    origin: str = Field(default="customer", description="Incident reporter origin")
    branch: Optional[str] = Field(default="central", description="Operational branch")
    status: str = Field(default="open", description="Initial lifecycle status")
    satisfaction_index: Optional[float] = Field(
        default=None, ge=1.0, le=5.0, description="Customer satisfaction rating"
    )
    legacy_id: Optional[str] = Field(
        default=None, description="Legacy CSV identifier for idempotency"
    )


class IncidentStatusUpdateDTO(BaseModel):
    """Payload for transitioning incident lifecycle status."""

    status: str = Field(..., description="Target lifecycle status")


class IncidentResponseDTO(BaseModel):
    """Standardized response payload for incident entities."""

    id: str
    title: str
    description: str
    category: str
    status: str
    origin: str
    branch: str
    satisfaction_index: Optional[float] = None
    created_at: str
    updated_at: str
    legacy_id: Optional[str] = None


class IncidentSummaryResponseDTO(BaseModel):
    """Aggregated 4-dimension metric breakdown."""

    total_incidents: int
    by_status: Dict[str, int]
    by_category: Dict[str, int]
    by_origin: Dict[str, int]
    by_branch: Dict[str, int]


class IncidentAnalysisResponseDTO(BaseModel):
    """Results from processing an incident CSV stream."""

    total_rows: int
    valid_rows: int
    invalid_rows: int
    category_breakdown: Dict[str, int]
    average_satisfaction: Optional[float] = None


__all__ = [
    "IncidentAnalysisResponseDTO",
    "IncidentCreateDTO",
    "IncidentResponseDTO",
    "IncidentStatusUpdateDTO",
    "IncidentSummaryResponseDTO",
]
