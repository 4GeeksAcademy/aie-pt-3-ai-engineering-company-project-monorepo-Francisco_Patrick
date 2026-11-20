"""Supplier application Data Transfer Objects (DTOs).

Defines request/response contracts for Supplier operations, strictly enforcing
validation rules before data touches persistence.
"""

from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from domain.suppliers.models import VALID_CATEGORIES, VALID_STATUSES


class SupplierCreateDTO(BaseModel):
    """Payload for creating a new supplier.

    Note: updated_at is system-generated and omitted from input.
    """

    model_config = {"extra": "ignore"}

    name: str = Field(..., min_length=1, description="Nombre comercial del proveedor")
    country: str = Field(..., min_length=1, description="País del contrato ('USA' o 'Spain')")
    categories: Optional[List[str]] = Field(default=None, description="Lista de categorías operativas (mínimo 1)")
    category: Optional[str] = Field(default=None, description="Legacy single category")
    rate_per_shipment: Optional[float] = Field(default=None, gt=0.0, description="Tarifa vigente por envío (> 0)")
    cost_per_kg: Optional[float] = Field(default=None, gt=0.0, description="Legacy rate field alias (> 0)")
    currency: Optional[str] = Field(default=None, description="'USD' para USA, 'EUR' para Spain")
    status: Literal["active", "suspended"] = Field(default="active", description="Estado operativo ('active' o 'suspended')")
    service_zone: Optional[str] = Field(default=None, description="Zona de cobertura del proveedor")
    contact_email: Optional[str] = Field(default=None, description="Email de contacto del proveedor")
    notes: Optional[str] = Field(default=None, description="Observaciones del equipo de operaciones")

    @model_validator(mode="before")
    @classmethod
    def sanitize_and_synchronize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Strip updated_at if a client attempts to pass it:
            data.pop("updated_at", None)

            # Synchronize rate_per_shipment and cost_per_kg
            rate = data.get("rate_per_shipment")
            cost = data.get("cost_per_kg")
            if rate is None and cost is not None:
                data["rate_per_shipment"] = cost
                rate = cost
            if cost is None and rate is not None:
                data["cost_per_kg"] = rate

            # Synchronize category and categories
            cats = data.get("categories")
            cat = data.get("category")
            if (not cats or len(cats) == 0) and cat:
                data["categories"] = [cat]

            # Normalize country if "United States"
            if data.get("country") == "United States":
                data["country"] = "USA"

            # Auto default currency if not supplied
            if not data.get("currency"):
                c = data.get("country")
                if c == "USA":
                    data["currency"] = "USD"
                elif c == "Spain":
                    data["currency"] = "EUR"

        return data

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Status must be one of {VALID_STATUSES}, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_business_constraints(self) -> "SupplierCreateDTO":
        # Ensure positive rate is provided
        if self.rate_per_shipment is None and self.cost_per_kg is None:
            raise ValueError("rate_per_shipment is required and must be strictly positive (> 0)")

        # Ensure categories list has at least 1 item
        if not self.categories or len(self.categories) == 0:
            raise ValueError("categories must contain at least 1 item")

        # Currency consistency with country
        if self.country == "USA" and self.currency and self.currency != "USD":
            raise ValueError("A supplier with country 'USA' must use currency 'USD'")
        if self.country == "Spain" and self.currency and self.currency != "EUR":
            raise ValueError("A supplier with country 'Spain' must use currency 'EUR'")

        return self


class SupplierUpdateRateDTO(BaseModel):
    """Payload for updating freight shipping rate."""

    rate_per_shipment: Optional[float] = Field(default=None, gt=0.0, description="New rate per shipment (> 0)")
    cost_per_kg: Optional[float] = Field(default=None, gt=0.0, description="New rate per kg alias (> 0)")

    @model_validator(mode="before")
    @classmethod
    def synchronize_rates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            rate = data.get("rate_per_shipment")
            cost = data.get("cost_per_kg")
            if rate is None and cost is not None:
                data["rate_per_shipment"] = cost
            elif cost is None and rate is not None:
                data["cost_per_kg"] = rate
        return data

    @property
    def effective_rate(self) -> float:
        if self.rate_per_shipment is not None and self.rate_per_shipment > 0:
            return self.rate_per_shipment
        if self.cost_per_kg is not None and self.cost_per_kg > 0:
            return self.cost_per_kg
        raise ValueError("A positive rate must be provided (> 0)")


class SupplierUpdateStatusDTO(BaseModel):
    """Payload for updating operational status."""

    status: Literal["active", "suspended"] = Field(..., description="Operational status ('active' or 'suspended')")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Status must be one of {VALID_STATUSES}, got '{v}'")
        return v


class SupplierResponseDTO(BaseModel):
    """Standardized response payload for supplier entities."""

    id: int
    name: str
    country: str
    categories: List[str]
    rate_per_shipment: float
    currency: str
    status: Literal["active", "suspended"]
    updated_at: Optional[str] = None
    service_zone: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None

    # Compatibility fields
    category: Optional[str] = None
    cost_per_kg: Optional[float] = None


__all__ = [
    "SupplierCreateDTO",
    "SupplierResponseDTO",
    "SupplierUpdateRateDTO",
    "SupplierUpdateStatusDTO",
]
