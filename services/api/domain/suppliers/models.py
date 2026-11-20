"""Supplier domain models and value objects.

Pure business entities for TrackFlow suppliers domain with zero framework dependencies.
Reflects exactly the fields and business rules defined in trackflow-BRIEFING.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


VALID_CATEGORIES = [
    "carrier_last_mile",
    "carrier_international",
    "warehouse_supplies",
    "packaging_materials",
    "reverse_logistics",
    "fleet_maintenance",
    "it_and_wms_software",
    "cleaning_and_facilities",
]

VALID_STATUSES = ["active", "suspended"]


class SupplierStatus(str, Enum):
    """Operational statuses permitted for TrackFlow suppliers."""

    active = "active"
    suspended = "suspended"


class Supplier(BaseModel):
    """Pure domain entity representing a TrackFlow supplier."""

    id: Optional[int] = Field(default=None, description="Unique numeric supplier identifier")
    name: str = Field(..., min_length=1, description="Nombre comercial del proveedor")
    country: str = Field(..., min_length=1, description="País del contrato ('USA' o 'Spain')")
    categories: List[str] = Field(..., min_length=1, description="Tipo de servicio o producto que provee")
    rate_per_shipment: float = Field(..., gt=0.0, description="Tarifa vigente por envío (> 0)")
    currency: str = Field(..., description="'USD' para USA, 'EUR' para Spain")
    updated_at: Optional[str] = Field(default=None, description="Timestamp de la última actualización de tarifa")
    status: Literal["active", "suspended"] = Field(..., description="Estado operativo ('active' o 'suspended')")
    service_zone: Optional[str] = Field(default=None, description="Zona de cobertura del proveedor")
    contact_email: Optional[str] = Field(default=None, description="Email de contacto del proveedor")
    notes: Optional[str] = Field(default=None, description="Observaciones del equipo de operaciones")

    # Compatibility fields for legacy consumers/tests/UI
    cost_per_kg: Optional[float] = Field(default=None, description="Legacy rate field alias")
    category: Optional[str] = Field(default=None, description="Legacy primary category")

    @model_validator(mode="before")
    @classmethod
    def populate_compatibility_and_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
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
            elif cats and not cat:
                data["category"] = cats[0]

            # Normalize country if "United States"
            if data.get("country") == "United States":
                data["country"] = "USA"

            # Auto-assign currency if missing based on country
            if not data.get("currency"):
                country = data.get("country")
                if country == "USA":
                    data["currency"] = "USD"
                elif country == "Spain":
                    data["currency"] = "EUR"
                else:
                    data["currency"] = "USD"

        return data

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Status must be one of {VALID_STATUSES}, got '{v}'")
        return v

    @field_validator("rate_per_shipment")
    @classmethod
    def validate_rate(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Tariff rate must be strictly positive (> 0)")
        return v

    @model_validator(mode="after")
    def validate_currency_country_consistency(self) -> "Supplier":
        if self.country == "USA" and self.currency != "USD":
            raise ValueError("A supplier with country 'USA' must use currency 'USD'")
        if self.country == "Spain" and self.currency != "EUR":
            raise ValueError("A supplier with country 'Spain' must use currency 'EUR'")
        return self


__all__ = [
    "Supplier",
    "SupplierStatus",
    "VALID_CATEGORIES",
    "VALID_STATUSES",
]
