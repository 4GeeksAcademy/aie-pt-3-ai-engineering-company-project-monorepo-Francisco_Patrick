from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class SKU(SQLModel, table=True):
    __tablename__ = "sku"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(index=True, unique=True, nullable=False)
    name: str = Field(nullable=False)
    warehouse_id: str = Field(index=True, nullable=False)
    low_stock_threshold: int = Field(default=10, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class StockEntry(SQLModel, table=True):
    __tablename__ = "stock_entry"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key="sku.id", index=True, nullable=False)
    warehouse_id: str = Field(index=True, nullable=False)
    quantity: int = Field(nullable=False)
    user_uuid: str = Field(index=True, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class StockExit(SQLModel, table=True):
    __tablename__ = "stock_exit"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key="sku.id", index=True, nullable=False)
    warehouse_id: str = Field(index=True, nullable=False)
    quantity: int = Field(nullable=False)
    user_uuid: str = Field(index=True, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

