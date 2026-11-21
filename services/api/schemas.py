"""Pydantic schemas for TrackFlow Inventory API request and response data structures."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class ProductBase(BaseModel):
    """Base schema for Product / SKU attributes."""

    sku: str = Field(..., min_length=1, description="Unique alphanumeric SKU code")
    name: str = Field(..., min_length=1, description="Product catalog name")
    client_name: Optional[str] = Field(
        default="PureStep Footwear", description="Brand client name"
    )
    category: Optional[str] = Field(
        default="fashion", description="Category (fashion, electronics, cosmetics)"
    )
    warehouse: Optional[str] = Field(
        default=None, description="Warehouse code: LA or ZGZ"
    )
    warehouse_id: Optional[str] = Field(
        default=None, description="Warehouse identifier"
    )
    low_stock_threshold: int = Field(
        default=10, ge=0, description="Minimum alert threshold"
    )

    @model_validator(mode="after")
    def sync_warehouses(self) -> "ProductBase":
        """Synchronize warehouse and warehouse_id fields."""
        wh = self.warehouse or self.warehouse_id or "LA"
        if not self.warehouse:
            object.__setattr__(self, "warehouse", wh)
        if not self.warehouse_id:
            object.__setattr__(self, "warehouse_id", wh)
        return self


class ProductCreateDTO(ProductBase):
    """Payload for creating a new product SKU."""

    pass


class ProductResponseDTO(BaseModel):
    """Standardized projection payload for product details with calculated stock."""

    id: int
    sku: str
    name: str
    client_name: str = "PureStep Footwear"
    category: str = "fashion"
    warehouse: str = "LA"
    warehouse_id: str = "LA"
    low_stock_threshold: int = 10
    current_stock: int
    is_low_stock: Optional[bool] = None
    created_at: Optional[datetime] = None


class InboundOrderCreateDTO(BaseModel):
    """Payload for registering an inbound stock shipment (StockEntry)."""

    sku_id: int = Field(..., description="Target SKU ID")
    warehouse: Optional[str] = Field(default=None, description="Warehouse code")
    warehouse_id: Optional[str] = Field(default=None, description="Warehouse code")
    quantity: int = Field(..., gt=0, description="Inbound units count")
    reference: Optional[str] = Field(
        default="", description="Customer shipment reference code"
    )

    @model_validator(mode="after")
    def sync_warehouses(self) -> "InboundOrderCreateDTO":
        """Synchronize warehouse and warehouse_id fields."""
        wh = self.warehouse or self.warehouse_id or "LA"
        if not self.warehouse:
            object.__setattr__(self, "warehouse", wh)
        if not self.warehouse_id:
            object.__setattr__(self, "warehouse_id", wh)
        return self


class OutboundOrderCreateDTO(BaseModel):
    """Payload for registering an outbound stock dispatch or loss (StockExit)."""

    sku_id: int = Field(..., description="Target SKU ID")
    warehouse: Optional[str] = Field(default=None, description="Warehouse code")
    warehouse_id: Optional[str] = Field(default=None, description="Warehouse code")
    quantity: int = Field(..., gt=0, description="Outbound units count")
    exit_type: Optional[str] = Field(
        default=None, description="Exit type: dispatch or loss"
    )
    tracking_number: Optional[str] = Field(
        default=None, description="Carrier tracking number"
    )

    @model_validator(mode="after")
    def validate_fields(self) -> "OutboundOrderCreateDTO":
        """Validate warehouse consistency and tracking number rules."""
        wh = self.warehouse or self.warehouse_id or "LA"
        if not self.warehouse:
            object.__setattr__(self, "warehouse", wh)
        if not self.warehouse_id:
            object.__setattr__(self, "warehouse_id", wh)

        if self.exit_type == "dispatch":
            if not self.tracking_number or not str(self.tracking_number).strip():
                raise ValueError("tracking_number is required when exit_type is 'dispatch'")
        elif self.exit_type == "loss":
            if self.tracking_number is not None:
                raise ValueError("tracking_number must be null when exit_type is 'loss'")
        return self


class OrderResponseDTO(BaseModel):
    """Standardized response payload for inventory order transaction."""

    id: int
    order_type: str
    sku_id: int
    sku_code: str
    reference: Optional[str] = None
    warehouse: str = "LA"
    warehouse_id: str = "LA"
    quantity: int
    exit_type: Optional[str] = None
    tracking_number: Optional[str] = None
    user_uuid: str
    created_at: Optional[datetime] = None


# Aliases for different naming conventions
ProductCreate = ProductCreateDTO
ProductResponse = ProductResponseDTO
SKUCreate = ProductCreateDTO
SKUResponse = ProductResponseDTO
InboundOrderCreate = InboundOrderCreateDTO
StockEntryCreate = InboundOrderCreateDTO
OutboundOrderCreate = OutboundOrderCreateDTO
StockExitCreate = OutboundOrderCreateDTO
OrderResponse = OrderResponseDTO
StockEntryResponse = OrderResponseDTO
StockExitResponse = OrderResponseDTO

__all__ = [
    "InboundOrderCreate",
    "InboundOrderCreateDTO",
    "OrderResponse",
    "OrderResponseDTO",
    "OutboundOrderCreate",
    "OutboundOrderCreateDTO",
    "ProductBase",
    "ProductCreate",
    "ProductCreateDTO",
    "ProductResponse",
    "ProductResponseDTO",
    "SKUCreate",
    "SKUResponse",
    "StockEntryCreate",
    "StockEntryResponse",
    "StockExitCreate",
    "StockExitResponse",
]
