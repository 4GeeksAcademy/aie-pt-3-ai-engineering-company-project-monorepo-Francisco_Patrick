"""Supplier domain driven port interfaces.

Defines the abstract repository contract for persisting and retrieving Supplier domain entities.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from domain.suppliers.models import Supplier


class SupplierRepositoryPort(ABC):
    """Driven port interface for Supplier storage operations."""

    @abstractmethod
    def create(self, supplier: Supplier) -> Supplier:
        """Persist a new supplier entity and return the saved instance with ID.

        Args:
            supplier: Pure domain Supplier instance to persist.

        Returns:
            Saved Supplier entity with assigned numeric ID.
        """
        ...

    @abstractmethod
    def get_by_id(self, supplier_id: int) -> Optional[Supplier]:
        """Retrieve a supplier by numeric ID.

        Args:
            supplier_id: Numeric primary key ID.

        Returns:
            Supplier entity if found, None otherwise.
        """
        ...

    @abstractmethod
    def list_all(
        self,
        country: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Supplier]:
        """List suppliers matching optional country and category filters.

        Args:
            country: Optional country string filter.
            category: Optional category string filter.

        Returns:
            List of matching Supplier domain entities.
        """
        ...

    @abstractmethod
    def update_rate(self, supplier_id: int, cost_per_kg: float) -> Optional[Supplier]:
        """Update shipping cost per kg for a supplier.

        Args:
            supplier_id: Numeric primary key ID.
            cost_per_kg: New positive rate per kg.

        Returns:
            Updated Supplier entity if found, None otherwise.
        """
        ...

    @abstractmethod
    def update_status(self, supplier_id: int, status: str) -> Optional[Supplier]:
        """Update operational status ('active' or 'suspended') for a supplier.

        Args:
            supplier_id: Numeric primary key ID.
            status: Target operational status.

        Returns:
            Updated Supplier entity if found, None otherwise.
        """
        ...

    @abstractmethod
    def delete(self, supplier_id: int) -> bool:
        """Delete a supplier record.

        Args:
            supplier_id: Numeric primary key ID.

        Returns:
            True if deleted, False if not found.
        """
        ...


__all__ = ["SupplierRepositoryPort"]
