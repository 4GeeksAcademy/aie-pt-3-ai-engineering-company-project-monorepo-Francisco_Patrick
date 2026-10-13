"""Inventory application Data Transfer Objects (DTOs)."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProductCreateDTO(BaseModel):
    """Payload for creating a new product SKU."""

    sku: str = Field(..., min_length=1, description="Unique alphanumeric SKU code")
    name: str = Field(..., min_length=1, description="Product catalog name")
    warehouse_id: str = Field(..., min_length=1, description="Warehouse code")
    low_stock_threshold: int = Field(default=10, ge=0, description="Minimum alert threshold")


class InboundOrderCreateDTO(BaseModel):
    """Payload for registering an inbound stock shipment."""

    sku_id: int = Field(..., description="Target SKU ID")
    warehouse_id: str = Field(..., min_length=1, description="Warehouse code")
    quantity: int = Field(..., gt=0, description="Inbound units count")


class OutboundOrderCreateDTO(BaseModel):
    """Payload for registering an outbound stock dispatch."""

    sku_id: int = Field(..., description="Target SKU ID")
    warehouse_id: str = Field(..., min_length=1, description="Warehouse code")
    quantity: int = Field(..., gt=0, description="Outbound units count")


class ProductResponseDTO(BaseModel):
    """Standardized projection payload for product details."""

    id: int
    sku: str
    name: str
    warehouse_id: str
    low_stock_threshold: int
    current_stock: int
    is_low_stock: Optional[bool] = None
    created_at: Optional[datetime] = None


class OrderResponseDTO(BaseModel):
    """Standardized response payload for inventory order transaction."""

    id: int
    order_type: str
    sku_id: int
    sku_code: str
    warehouse_id: str
    quantity: int
    user_uuid: str
    created_at: Optional[datetime] = None


__all__ = [
    "InboundOrderCreateDTO",
    "OrderResponseDTO",
    "OutboundOrderCreateDTO",
    "ProductCreateDTO",
    "ProductResponseDTO",
]
