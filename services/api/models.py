from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime

class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)
    categories: List[str] = Field(..., min_length=1)
    cost_per_kg: float = Field(..., gt=0, description="Cost per kg must be strictly positive")
    status: Literal["active", "suspended"] = Field(...)

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdateRate(BaseModel):
    cost_per_kg: float = Field(..., gt=0)

class SupplierUpdateStatus(BaseModel):
    status: Literal["active", "suspended"] = Field(...)

class Supplier(SupplierBase):
    id: int
    updated_at: str
