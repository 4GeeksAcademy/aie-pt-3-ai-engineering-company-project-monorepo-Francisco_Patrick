"""Backward-compatible re-export of models (relational ORM + Supplier domain models).

Maintained for route, schema, and legacy compatibility.
"""

from domain.suppliers.models import (
    Supplier,
    SupplierStatus,
    VALID_CATEGORIES,
    VALID_STATUSES,
)
from infrastructure.persistence.sqlmodel.models import (
    SKU,
    StockEntry,
    StockExit,
    TelemetryEventRecord,
)

__all__ = [
    "SKU",
    "StockEntry",
    "StockExit",
    "Supplier",
    "SupplierStatus",
    "TelemetryEventRecord",
    "VALID_CATEGORIES",
    "VALID_STATUSES",
]
