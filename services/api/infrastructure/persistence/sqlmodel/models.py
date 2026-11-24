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


class IntakeTicketTable(SQLModel, table=True):
    """Relational table model for RFP intake tickets."""

    __tablename__ = "intake_tickets"

    id: UUID = Field(primary_key=True, index=True, nullable=False)
    ticket_number: str = Field(unique=True, index=True, nullable=False)
    status: str = Field(index=True, nullable=False)
    raw_pdf_path: str = Field(nullable=False)
    raw_pdf_filename: str = Field(nullable=False)
    file_size_bytes: int = Field(nullable=False)
    rejection_reason: Optional[str] = Field(default=None, nullable=True)
    error_message: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )


class RFPMetadataTable(SQLModel, table=True):
    """Relational table model for extracted RFP commercial metadata."""

    __tablename__ = "rfp_metadata"

    id: UUID = Field(primary_key=True, index=True, nullable=False)
    ticket_id: UUID = Field(
        foreign_key="intake_tickets.id", unique=True, index=True, nullable=False
    )
    client_name: str = Field(nullable=False)
    client_country: str = Field(nullable=False)
    currency: str = Field(nullable=False)
    services_requested: List[str] = Field(
        default_factory=list,
        sa_column=SAColumn(JSON, nullable=False),
    )
    monthly_volume: Optional[int] = Field(default=None, nullable=True)
    deadline: Optional[str] = Field(default=None, nullable=True)
    budget_range: Optional[str] = Field(default=None, nullable=True)
    departments_needed: List[str] = Field(
        default_factory=list,
        sa_column=SAColumn(JSON, nullable=False),
    )
    unsupported_services: List[str] = Field(
        default_factory=list,
        sa_column=SAColumn(JSON, nullable=False),
    )
    readability_scores: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=SAColumn(JSON, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )


class DepartmentSectionTable(SQLModel, table=True):
    """Relational table model for department worker evaluations and Part 2 drafts."""

    __tablename__ = "department_sections"

    id: UUID = Field(primary_key=True, index=True, nullable=False)
    ticket_id: UUID = Field(
        foreign_key="intake_tickets.id", index=True, nullable=False
    )
    department_id: str = Field(index=True, nullable=False)
    department_name: str = Field(nullable=False)
    responsible_person: str = Field(nullable=False)
    key_aspects: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=SAColumn(JSON, nullable=False),
    )
    open_questions: List[str] = Field(
        default_factory=list,
        sa_column=SAColumn(JSON, nullable=False),
    )
    policy_warnings: List[str] = Field(
        default_factory=list,
        sa_column=SAColumn(JSON, nullable=False),
    )
    draft_content: Optional[str] = Field(default=None, nullable=True)
    iteration: int = Field(default=0, nullable=False)
    status: str = Field(default="pending", index=True, nullable=False)
    evaluation_results: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=SAColumn(JSON, nullable=False),
    )
    approval_status: str = Field(default="pending", index=True, nullable=False)
    approver: Optional[str] = Field(default=None, nullable=True)
    review_feedback: Optional[str] = Field(default=None, nullable=True)
    approved_at: Optional[datetime] = Field(
        default=None,
        sa_column=SAColumn(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )


class IntakeHandoffPayloadTable(SQLModel, table=True):
    """Relational table model for canonical Part 2 handoff payloads."""

    __tablename__ = "intake_handoff_payloads"

    id: UUID = Field(primary_key=True, index=True, nullable=False)
    ticket_id: UUID = Field(
        foreign_key="intake_tickets.id", unique=True, index=True, nullable=False
    )
    schema_version: str = Field(default="1.0.0", nullable=False)
    executive_summary: str = Field(nullable=False)
    flagged_contradictions: List[str] = Field(
        default_factory=list,
        sa_column=SAColumn(JSON, nullable=False),
    )
    key_questions_for_prospect: List[str] = Field(
        default_factory=list,
        sa_column=SAColumn(JSON, nullable=False),
    )
    internal_contacts: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=SAColumn(JSON, nullable=False),
    )
    full_handoff_json: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=SAColumn(JSON, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )


class Part3HandoffPayloadTable(SQLModel, table=True):
    """Relational table model for canonical Part 3 proposal approval handoff payloads."""

    __tablename__ = "part3_handoff_payloads"

    id: UUID = Field(primary_key=True, index=True, nullable=False)
    ticket_id: UUID = Field(
        foreign_key="intake_tickets.id", unique=True, index=True, nullable=False
    )
    schema_version: str = Field(default="2.0.0", nullable=False)
    overall_status: str = Field(index=True, nullable=False)
    rfp_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=SAColumn(JSON, nullable=False),
    )
    department_sections: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=SAColumn(JSON, nullable=False),
    )
    emitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )


class ArbitrationLogTable(SQLModel, table=True):
    """Relational table model for deterministic conflict arbitration audit records (Part 3)."""

    __tablename__ = "arbitration_logs"

    id: UUID = Field(primary_key=True, index=True, nullable=False)
    ticket_id: UUID = Field(
        foreign_key="intake_tickets.id", index=True, nullable=False
    )
    trigger_id: str = Field(index=True, nullable=False)
    arbiter: str = Field(nullable=False)
    rule_applied: str = Field(nullable=False)
    resolution_details: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=SAColumn(JSON, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )


class FinalDocumentTable(SQLModel, table=True):
    """Relational table model for synthesized final commercial proposal documents (Part 3)."""

    __tablename__ = "final_documents"

    id: UUID = Field(primary_key=True, index=True, nullable=False)
    ticket_id: UUID = Field(
        foreign_key="intake_tickets.id", unique=True, index=True, nullable=False
    )
    title: str = Field(nullable=False)
    client_name: str = Field(nullable=False)
    currency: str = Field(nullable=False)
    executive_summary: str = Field(nullable=False)
    sections: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=SAColumn(JSON, nullable=False),
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )


__all__ = [
    "ArbitrationLogTable",
    "DepartmentSectionTable",
    "FinalDocumentTable",
    "IntakeHandoffPayloadTable",
    "IntakeTicketTable",
    "Part3HandoffPayloadTable",
    "RFPMetadataTable",
    "SKU",
    "StockEntry",
    "StockExit",
    "TelemetryEventRecord",
]
