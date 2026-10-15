"""Backward-compatible re-export of relational ORM models.

Maintained for legacy route and schema compatibility until Phase 5 consolidation.
"""

from infrastructure.persistence.sqlmodel.models import SKU, StockEntry, StockExit

__all__ = ["SKU", "StockEntry", "StockExit"]
