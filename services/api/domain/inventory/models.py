"""Inventory domain models and calculated projections.

Pure business entities for TrackFlow inventory domain with zero framework or database dependencies.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SKU(BaseModel):
    """Stock Keeping Unit catalog domain entity."""

    id: Optional[int] = Field(default=None, description="Unique numeric primary key ID")
    sku: str = Field(..., min_length=1, description="Unique alphanumeric SKU code")
    name: str = Field(..., min_length=1, description="Human-readable product name")
    warehouse_id: str = Field(..., min_length=1, description="Primary warehouse identifier")
    low_stock_threshold: int = Field(default=10, ge=0, description="Minimum alert threshold (>= 0)")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")


class StockEntry(BaseModel):
    """Inbound stock arrival transaction entity."""

    id: Optional[int] = Field(default=None, description="Unique transaction ID")
    sku_id: int = Field(..., description="Referenced SKU foreign key ID")
    warehouse_id: str = Field(..., min_length=1, description="Target warehouse identifier")
    quantity: int = Field(..., gt=0, description="Inbound item count (strictly positive)")
    user_uuid: str = Field(default="", description="Operator user identifier")
    date: Optional[str] = Field(default=None, description="Optional ISO transaction date string")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")


class StockExit(BaseModel):
    """Outbound stock dispatch transaction entity."""

    id: Optional[int] = Field(default=None, description="Unique transaction ID")
    sku_id: int = Field(..., description="Referenced SKU foreign key ID")
    warehouse_id: str = Field(..., min_length=1, description="Source warehouse identifier")
    quantity: int = Field(..., gt=0, description="Outbound item count (strictly positive)")
    user_uuid: str = Field(default="", description="Operator user identifier")
    date: Optional[str] = Field(default=None, description="Optional ISO transaction date string")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")


class InventoryProduct(BaseModel):
    """Calculated domain projection representing product with dynamic stock metrics."""

    id: int = Field(..., description="SKU primary key ID")
    sku: str = Field(..., description="Unique alphanumeric SKU code")
    name: str = Field(..., description="Product name")
    warehouse_id: str = Field(..., description="Warehouse identifier")
    current_stock: int = Field(..., description="Dynamically computed net stock level")
    low_stock_threshold: int = Field(..., description="Low stock threshold")
    is_low_stock: bool = Field(..., description="True if current_stock <= low_stock_threshold")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")


__all__ = ["SKU", "InventoryProduct", "StockEntry", "StockExit"]
