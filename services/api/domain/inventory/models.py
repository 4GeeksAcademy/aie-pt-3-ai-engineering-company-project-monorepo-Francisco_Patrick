"""Inventory domain models and calculated projections.

Pure business entities for TrackFlow inventory domain with zero framework or database dependencies.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class SKU(BaseModel):
    """Stock Keeping Unit catalog domain entity."""

    id: Optional[int] = Field(default=None, description="Unique numeric primary key ID")
    sku: str = Field(..., min_length=1, description="Unique alphanumeric SKU code")
    name: str = Field(..., min_length=1, description="Human-readable product name")
    client_name: str = Field(default="PureStep Footwear", description="Brand client name")
    category: str = Field(default="fashion", description="Category: fashion, electronics, cosmetics")
    warehouse: str = Field(default="LA", description="Warehouse location")
    warehouse_id: str = Field(default="LA", description="Primary warehouse identifier")
    low_stock_threshold: int = Field(default=10, ge=0, description="Minimum alert threshold (>= 0)")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")

    @model_validator(mode="after")
    def sync_warehouses(self) -> "SKU":
        wh = self.warehouse or self.warehouse_id or "LA"
        if not self.warehouse:
            object.__setattr__(self, "warehouse", wh)
        if not self.warehouse_id:
            object.__setattr__(self, "warehouse_id", wh)
        return self


class StockEntry(BaseModel):
    """Inbound stock arrival transaction entity."""

    id: Optional[int] = Field(default=None, description="Unique transaction ID")
    sku_id: int = Field(..., description="Referenced SKU foreign key ID")
    warehouse: str = Field(default="LA", description="Target warehouse identifier")
    warehouse_id: str = Field(default="LA", description="Target warehouse identifier")
    quantity: int = Field(..., gt=0, description="Inbound item count (strictly positive)")
    reference: str = Field(default="", description="Customer shipment reference code")
    user_uuid: str = Field(default="", description="Operator user identifier")
    date: Optional[str] = Field(default=None, description="Optional ISO transaction date string")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")

    @model_validator(mode="after")
    def sync_warehouses(self) -> "StockEntry":
        wh = self.warehouse or self.warehouse_id or "LA"
        if not self.warehouse:
            object.__setattr__(self, "warehouse", wh)
        if not self.warehouse_id:
            object.__setattr__(self, "warehouse_id", wh)
        return self


class StockExit(BaseModel):
    """Outbound stock dispatch transaction entity."""

    id: Optional[int] = Field(default=None, description="Unique transaction ID")
    sku_id: int = Field(..., description="Referenced SKU foreign key ID")
    warehouse: str = Field(default="LA", description="Source warehouse identifier")
    warehouse_id: str = Field(default="LA", description="Source warehouse identifier")
    quantity: int = Field(..., gt=0, description="Outbound item count (strictly positive)")
    exit_type: str = Field(default="dispatch", description="Type of exit: dispatch or loss")
    tracking_number: Optional[str] = Field(default=None, description="Carrier tracking number")
    user_uuid: str = Field(default="", description="Operator user identifier")
    date: Optional[str] = Field(default=None, description="Optional ISO transaction date string")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")

    @model_validator(mode="after")
    def sync_warehouses(self) -> "StockExit":
        wh = self.warehouse or self.warehouse_id or "LA"
        if not self.warehouse:
            object.__setattr__(self, "warehouse", wh)
        if not self.warehouse_id:
            object.__setattr__(self, "warehouse_id", wh)
        return self


class InventoryProduct(BaseModel):
    """Calculated domain projection representing product with dynamic stock metrics."""

    id: int = Field(..., description="SKU primary key ID")
    sku: str = Field(..., description="Unique alphanumeric SKU code")
    name: str = Field(..., description="Product name")
    client_name: str = Field(default="PureStep Footwear", description="Brand client name")
    category: str = Field(default="fashion", description="Category: fashion, electronics, cosmetics")
    warehouse: str = Field(default="LA", description="Warehouse identifier")
    warehouse_id: str = Field(default="LA", description="Warehouse identifier")
    current_stock: int = Field(..., description="Dynamically computed net stock level")
    low_stock_threshold: int = Field(default=10, description="Low stock threshold")
    is_low_stock: bool = Field(default=False, description="True if current_stock <= low_stock_threshold")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")


__all__ = ["SKU", "InventoryProduct", "StockEntry", "StockExit"]
