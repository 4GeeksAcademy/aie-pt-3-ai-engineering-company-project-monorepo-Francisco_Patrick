"""SQLModel ORM relational table models.

Encapsulated exclusively within driven persistence adapter to prevent ORM leakage
into pure domain layers.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


class SKU(SQLModel, table=True):
    """Relational table model for SKU catalog."""

    __tablename__ = "sku"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(index=True, unique=True, nullable=False)
    name: str = Field(nullable=False)
    warehouse_id: str = Field(index=True, nullable=False)
    low_stock_threshold: int = Field(default=10, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )


class StockEntry(SQLModel, table=True):
    """Relational table model for inbound inventory shipments."""

    __tablename__ = "stock_entry"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key="sku.id", index=True, nullable=False)
    warehouse_id: str = Field(index=True, nullable=False)
    quantity: int = Field(nullable=False)
    user_uuid: str = Field(index=True, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )


class StockExit(SQLModel, table=True):
    """Relational table model for outbound inventory shipments."""

    __tablename__ = "stock_exit"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key="sku.id", index=True, nullable=False)
    warehouse_id: str = Field(index=True, nullable=False)
    quantity: int = Field(nullable=False)
    user_uuid: str = Field(index=True, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )


__all__ = ["SKU", "StockEntry", "StockExit"]
