from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    sku: str
    name: str
    warehouse_id: str
    low_stock_threshold: int = 10


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    warehouse_id: str
    low_stock_threshold: int
    current_stock: int
    created_at: datetime


class InboundOrderCreate(BaseModel):
    sku_id: int
    warehouse_id: str
    quantity: int = Field(gt=0)


class OutboundOrderCreate(BaseModel):
    sku_id: int
    warehouse_id: str
    quantity: int = Field(gt=0)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_type: str
    sku_id: int
    sku_code: str
    warehouse_id: str
    quantity: int
    user_uuid: str
    created_at: datetime

