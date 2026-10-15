"""Supplier application service orchestrating use cases with repository and cache ports."""

from typing import List, Optional

from application.suppliers.dto import SupplierCreateDTO
from domain.common.exceptions import EntityNotFoundError
from domain.common.ports import CachePort
from domain.suppliers.models import Supplier
from domain.suppliers.ports import SupplierRepositoryPort


class SupplierService:
    """Application orchestration service for the Suppliers functional domain."""

    def __init__(
        self,
        supplier_repo: SupplierRepositoryPort,
        cache: Optional[CachePort] = None,
    ) -> None:
        """Initialize service with injected repository and optional cache port."""
        self._repo = supplier_repo
        self._cache = cache

    def create_supplier(self, dto: SupplierCreateDTO) -> Supplier:
        """Create and persist a new supplier, invalidating cache namespace upon write."""
        supplier = Supplier(
            name=dto.name,
            country=dto.country,
            category=dto.category,
            categories=dto.categories,
            cost_per_kg=dto.cost_per_kg,
            status=dto.status,
        )
        saved = self._repo.create(supplier)

        if self._cache is not None:
            self._cache.invalidate_prefix("suppliers:")

        return saved

    def get_supplier_by_id(self, supplier_id: int) -> Supplier:
        """Retrieve supplier by numeric ID with caching."""
        cache_key = f"suppliers:{supplier_id}"
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return Supplier(**cached) if isinstance(cached, dict) else cached

        supplier = self._repo.get_by_id(supplier_id)
        if not supplier:
            raise EntityNotFoundError(entity_name="Supplier", entity_id=supplier_id)

        if self._cache is not None:
            self._cache.set(cache_key, supplier.model_dump(), ttl_seconds=60)

        return supplier

    def list_suppliers(
        self, country: Optional[str] = None, category: Optional[str] = None
    ) -> List[Supplier]:
        """List suppliers matching optional filters with query-parameter isolated caching."""
        cache_key = f"suppliers:country={country or ''}&category={category or ''}"
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                if isinstance(cached, list):
                    return [Supplier(**item) if isinstance(item, dict) else item for item in cached]
                return cached

        suppliers = self._repo.list_all(country=country, category=category)

        if self._cache is not None:
            self._cache.set(
                cache_key,
                [s.model_dump() for s in suppliers],
                ttl_seconds=60,
            )

        return suppliers

    def update_supplier_rate(self, supplier_id: int, cost_per_kg: float) -> Supplier:
        """Update shipping rate per kg, invalidating cached entries."""
        if cost_per_kg <= 0:
            from domain.common.exceptions import BusinessRuleViolationError
            raise BusinessRuleViolationError("Cost per kg must be strictly positive.")

        updated = self._repo.update_rate(supplier_id, cost_per_kg)
        if not updated:
            raise EntityNotFoundError(entity_name="Supplier", entity_id=supplier_id)

        if self._cache is not None:
            self._cache.invalidate_prefix("suppliers:")

        return updated

    def update_supplier_status(self, supplier_id: int, status: str) -> Supplier:
        """Update supplier operational status, invalidating cached entries."""
        updated = self._repo.update_status(supplier_id, status)
        if not updated:
            raise EntityNotFoundError(entity_name="Supplier", entity_id=supplier_id)

        if self._cache is not None:
            self._cache.invalidate_prefix("suppliers:")

        return updated

    def delete_supplier(self, supplier_id: int) -> bool:
        """Delete supplier record, invalidating cache namespace."""
        deleted = self._repo.delete(supplier_id)
        if not deleted:
            raise EntityNotFoundError(entity_name="Supplier", entity_id=supplier_id)

        if self._cache is not None:
            self._cache.invalidate_prefix("suppliers:")

        return True


__all__ = ["SupplierService"]
