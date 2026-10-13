"""Supplier application Data Transfer Objects (DTOs)."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class SupplierCreateDTO(BaseModel):
    """Payload for creating a new supplier."""

    name: str = Field(..., min_length=1, description="Supplier name")
    country: str = Field(..., min_length=1, description="Country of origin")
    category: Optional[str] = Field(default=None, description="Primary category")
    categories: Optional[List[str]] = Field(default=None, description="List of categories")
    cost_per_kg: float = Field(..., gt=0.0, description="Rate per kg (strictly positive)")
    status: Literal["active", "suspended"] = Field(default="active", description="Initial status")


class SupplierUpdateRateDTO(BaseModel):
    """Payload for updating freight shipping rate."""

    cost_per_kg: float = Field(..., gt=0.0, description="New cost per kg")


class SupplierUpdateStatusDTO(BaseModel):
    """Payload for updating operational status."""

    status: Literal["active", "suspended"] = Field(..., description="Operational status")


class SupplierResponseDTO(BaseModel):
    """Standardized response payload for supplier entities."""

    id: int
    name: str
    country: str
    category: Optional[str] = None
    categories: Optional[List[str]] = None
    cost_per_kg: float
    status: Literal["active", "suspended"]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


__all__ = [
    "SupplierCreateDTO",
    "SupplierResponseDTO",
    "SupplierUpdateRateDTO",
    "SupplierUpdateStatusDTO",
]
