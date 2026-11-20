"""SQLModel ORM relational table models.

Encapsulated exclusively within driven persistence adapter to prevent ORM leakage
into pure domain layers.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import Column as SAColumn, DateTime, JSON
from sqlmodel import Column, Field, Relationship, SQLModel


class SKU(SQLModel, table=True):
    """Relational table model for SKU catalog."""

    __tablename__ = "sku"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(index=True, unique=True, nullable=False)
    name: str = Field(nullable=False)
    client_name: str = Field(default="PureStep Footwear", nullable=False)
    category: str = Field(default="fashion", nullable=False)
    warehouse: str = Field(default="LA", index=True, nullable=False)
    warehouse_id: str = Field(default="LA", index=True, nullable=False)
    low_stock_threshold: int = Field(default=10, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    entries: List["StockEntry"] = Relationship(back_populates="sku")
    exits: List["StockExit"] = Relationship(back_populates="sku")

    def __init__(self, **data: Any) -> None:
        if "warehouse" in data and "warehouse_id" not in data:
            data["warehouse_id"] = data["warehouse"]
        elif "warehouse_id" in data and "warehouse" not in data:
            data["warehouse"] = data["warehouse_id"]
        super().__init__(**data)


class StockEntry(SQLModel, table=True):
    """Relational table model for inbound inventory shipments."""

    __tablename__ = "stock_entry"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key="sku.id", index=True, nullable=False)
    warehouse: str = Field(default="LA", index=True, nullable=False)
    warehouse_id: str = Field(default="LA", index=True, nullable=False)
    quantity: int = Field(nullable=False)
    reference: str = Field(default="", nullable=False)
    user_uuid: str = Field(index=True, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    sku: Optional[SKU] = Relationship(back_populates="entries")

    def __init__(self, **data: Any) -> None:
        if "warehouse" in data and "warehouse_id" not in data:
            data["warehouse_id"] = data["warehouse"]
        elif "warehouse_id" in data and "warehouse" not in data:
            data["warehouse"] = data["warehouse_id"]
        super().__init__(**data)


class StockExit(SQLModel, table=True):
    """Relational table model for outbound inventory shipments."""

    __tablename__ = "stock_exit"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key="sku.id", index=True, nullable=False)
    warehouse: str = Field(default="LA", index=True, nullable=False)
    warehouse_id: str = Field(default="LA", index=True, nullable=False)
    quantity: int = Field(nullable=False)
    exit_type: str = Field(default="dispatch", nullable=False)
    tracking_number: Optional[str] = Field(default=None, nullable=True)
    user_uuid: str = Field(index=True, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    sku: Optional[SKU] = Relationship(back_populates="exits")

    def __init__(self, **data: Any) -> None:
        if "warehouse" in data and "warehouse_id" not in data:
            data["warehouse_id"] = data["warehouse"]
        elif "warehouse_id" in data and "warehouse" not in data:
            data["warehouse"] = data["warehouse_id"]
        super().__init__(**data)


class TelemetryEventRecord(SQLModel, table=True):
    """Relational table model for immutable telemetry events."""

    __tablename__ = "telemetry_events"

    event_id: UUID = Field(primary_key=True, index=True, nullable=False)
    timestamp: datetime = Field(
        sa_column=SAColumn(DateTime(timezone=True), index=True, nullable=False),
    )
    session_id: str = Field(index=True, nullable=False)
    user_id: Optional[str] = Field(default=None, index=True, nullable=True)
    event_type: str = Field(index=True, nullable=False)
    schema_version: str = Field(nullable=False)
    request_id: str = Field(index=True, nullable=False)
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=SAColumn(JSON, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )


__all__ = ["SKU", "StockEntry", "StockExit", "TelemetryEventRecord"]
