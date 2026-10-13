"""Inventory domain driven port interfaces.

Defines the abstract repository contract for managing SKUs, inbound entries, outbound exits,
and dynamic stock computations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from domain.inventory.models import SKU, InventoryProduct, StockEntry, StockExit


class InventoryRepositoryPort(ABC):
    """Driven port interface for Inventory storage operations."""

    @abstractmethod
    def create_sku(self, sku: SKU) -> SKU:
        """Create a new SKU in the catalog.

        Args:
            sku: Pure domain SKU entity.

        Returns:
            Saved SKU entity with assigned ID.
        """
        ...

    @abstractmethod
    def get_sku_by_id(self, sku_id: int) -> Optional[SKU]:
        """Retrieve an SKU by internal primary key ID.

        Args:
            sku_id: Numeric SKU ID.

        Returns:
            SKU entity if found, None otherwise.
        """
        ...

    @abstractmethod
    def get_sku_by_code(self, sku_code: str) -> Optional[SKU]:
        """Retrieve an SKU by unique alphanumeric code.

        Args:
            sku_code: Unique SKU string code.

        Returns:
            SKU entity if found, None otherwise.
        """
        ...

    @abstractmethod
    def list_all_products(self) -> List[InventoryProduct]:
        """Retrieve all catalog products with calculated current stock levels.

        Returns:
            List of InventoryProduct projections.
        """
        ...

    @abstractmethod
    def get_product_by_id(self, sku_id: int) -> Optional[InventoryProduct]:
        """Retrieve a single product with calculated current stock level.

        Args:
            sku_id: Numeric SKU ID.

        Returns:
            InventoryProduct projection if found, None otherwise.
        """
        ...

    @abstractmethod
    def calculate_stock(self, sku_id: int, warehouse_id: str) -> int:
        """Calculate current net stock (Inbound minus Outbound) for an SKU in a warehouse.

        Args:
            sku_id: Numeric SKU ID.
            warehouse_id: Warehouse identifier.

        Returns:
            Net integer stock quantity (>= 0).
        """
        ...

    @abstractmethod
    def add_inbound_entry(self, entry: StockEntry) -> StockEntry:
        """Append an inbound stock arrival transaction.

        Args:
            entry: Inbound stock entry to record.

        Returns:
            Persisted StockEntry record.
        """
        ...

    @abstractmethod
    def add_outbound_exit(self, exit_rec: StockExit) -> StockExit:
        """Append an outbound stock dispatch transaction.

        Args:
            exit_rec: Outbound stock exit to record.

        Returns:
            Persisted StockExit record.
        """
        ...

    @abstractmethod
    def list_orders(self) -> List[Dict[str, Any]]:
        """List chronological order history joined with SKU data.

        Returns:
            List of order dictionaries sorted by creation date descending.
        """
        ...


__all__ = ["InventoryRepositoryPort"]
