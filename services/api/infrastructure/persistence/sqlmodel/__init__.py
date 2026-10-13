"""SQLModel driven persistence adapters package."""

from infrastructure.persistence.sqlmodel.client import (
    SQLModelClientManager,
    engine,
    get_db,
    get_engine,
    init_db,
    sqlmodel_manager,
)
from infrastructure.persistence.sqlmodel.inventory_repository import (
    SQLModelInventoryRepository,
)
from infrastructure.persistence.sqlmodel.models import SKU, StockEntry, StockExit

__all__ = [
    "SKU",
    "SQLModelClientManager",
    "SQLModelInventoryRepository",
    "StockEntry",
    "StockExit",
    "engine",
    "get_db",
    "get_engine",
    "init_db",
    "sqlmodel_manager",
]
