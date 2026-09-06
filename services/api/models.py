from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime

class SupplierStatus(str, Enum):
    active = "active"
    suspended = "suspended"

class SupplierBase(BaseModel):
    name: str = Field(..., description="Name of the supplier (e.g. FedEx, UPS)")
    country: str = Field(..., description="Operating country (e.g. Spain, United States)")
    categories: List[str] = Field(default_factory=list, description="Supported product categories")
    cost_per_kg: float = Field(..., gt=0, description="Rate per kg, must be positive")
    status: SupplierStatus = Field(default=SupplierStatus.active, description="Current operational status")

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdateRate(BaseModel):
    cost_per_kg: float = Field(..., gt=0)

class SupplierUpdateStatus(BaseModel):
    status: SupplierStatus

class SupplierInDB(SupplierBase):
    id: int
    updated_at: datetime
