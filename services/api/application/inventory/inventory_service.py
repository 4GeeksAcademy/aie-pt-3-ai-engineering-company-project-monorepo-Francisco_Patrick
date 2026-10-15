"""Inventory application service orchestrating catalog and stock movements."""

from typing import Any, Dict, List, Optional

from application.inventory.dto import (
    InboundOrderCreateDTO,
    OrderResponseDTO,
    OutboundOrderCreateDTO,
    ProductCreateDTO,
)
from domain.common.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    InsufficientStockError,
)
from domain.common.ports import CachePort
from domain.inventory.models import InventoryProduct, SKU, StockEntry, StockExit
from domain.inventory.ports import InventoryRepositoryPort


class InventoryService:
    """Application orchestration service for the Inventory functional domain."""

    def __init__(
        self,
        inventory_repo: InventoryRepositoryPort,
        cache: Optional[CachePort] = None,
    ) -> None:
        """Initialize service with injected repository and optional cache port."""
        self._repo = inventory_repo
        self._cache = cache

    def create_product(self, dto: ProductCreateDTO) -> InventoryProduct:
        """Create and persist a new product SKU with duplicate code detection."""
        existing = self._repo.get_sku_by_code(dto.sku)
        if existing:
            raise DuplicateEntityError(
                entity_name="Product SKU", field="sku", value=dto.sku
            )

        sku = SKU(
            sku=dto.sku,
            name=dto.name,
            warehouse_id=dto.warehouse_id,
            low_stock_threshold=dto.low_stock_threshold,
        )
        saved_sku = self._repo.create_sku(sku)
        if saved_sku.id is None:
            raise RuntimeError("Failed to obtain persistent ID for created SKU")

        stock = self._repo.calculate_stock(saved_sku.id, saved_sku.warehouse_id)

        if self._cache is not None:
            self._cache.invalidate_prefix("inventory_products:")

        return InventoryProduct(
            id=saved_sku.id,
            sku=saved_sku.sku,
            name=saved_sku.name,
            warehouse_id=saved_sku.warehouse_id,
            current_stock=stock,
            low_stock_threshold=saved_sku.low_stock_threshold,
            is_low_stock=stock <= saved_sku.low_stock_threshold,
            created_at=saved_sku.created_at,
        )

    def list_products(self) -> List[InventoryProduct]:
        """List all products with dynamically calculated net stock levels."""
        cache_key = "inventory_products:all"
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                if isinstance(cached, list):
                    return [
                        InventoryProduct(**item) if isinstance(item, dict) else item
                        for item in cached
                    ]
                return cached

        products = self._repo.list_all_products()

        if self._cache is not None:
            self._cache.set(
                cache_key,
                [p.model_dump() for p in products],
                ttl_seconds=30,
            )

        return products

    def get_product_by_id(self, product_id: int) -> InventoryProduct:
        """Retrieve a product by ID with calculated stock level."""
        cache_key = f"inventory_products:{product_id}"
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return (
                    InventoryProduct(**cached)
                    if isinstance(cached, dict)
                    else cached
                )

        product = self._repo.get_product_by_id(product_id)
        if not product:
            raise EntityNotFoundError(entity_name="Product", entity_id=product_id)

        if self._cache is not None:
            self._cache.set(cache_key, product.model_dump(), ttl_seconds=30)

        return product

    def calculate_stock(self, sku_id: int, warehouse_id: str) -> int:
        """Calculate current net inventory stock for an SKU in a warehouse."""
        return self._repo.calculate_stock(sku_id, warehouse_id)

    def create_inbound_order(
        self, dto: InboundOrderCreateDTO, user_uuid: str
    ) -> OrderResponseDTO:
        """Record an inbound stock arrival transaction and invalidate products cache."""
        sku = self._repo.get_sku_by_id(dto.sku_id)
        if not sku:
            raise EntityNotFoundError(entity_name="Product", entity_id=dto.sku_id)

        entry = StockEntry(
            sku_id=dto.sku_id,
            warehouse_id=dto.warehouse_id,
            quantity=dto.quantity,
            user_uuid=user_uuid,
        )
        saved_entry = self._repo.add_inbound_entry(entry)
        if saved_entry.id is None:
            raise RuntimeError("Failed to persist inbound stock transaction")

        if self._cache is not None:
            self._cache.invalidate_prefix("inventory_products:")

        return OrderResponseDTO(
            id=saved_entry.id,
            order_type="inbound",
            sku_id=saved_entry.sku_id,
            sku_code=sku.sku,
            warehouse_id=saved_entry.warehouse_id,
            quantity=saved_entry.quantity,
            user_uuid=saved_entry.user_uuid,
            created_at=saved_entry.created_at,
        )

    def create_outbound_order(
        self, dto: OutboundOrderCreateDTO, user_uuid: str
    ) -> OrderResponseDTO:
        """Record an outbound stock exit transaction enforcing strict stock invariants."""
        sku = self._repo.get_sku_by_id(dto.sku_id)
        if not sku:
            raise EntityNotFoundError(entity_name="Product", entity_id=dto.sku_id)

        current_stock = self._repo.calculate_stock(dto.sku_id, dto.warehouse_id)
        if current_stock < dto.quantity:
            raise InsufficientStockError(
                sku_id=dto.sku_id,
                available=current_stock,
                requested=dto.quantity,
            )

        exit_rec = StockExit(
            sku_id=dto.sku_id,
            warehouse_id=dto.warehouse_id,
            quantity=dto.quantity,
            user_uuid=user_uuid,
        )
        saved_exit = self._repo.add_outbound_exit(exit_rec)
        if saved_exit.id is None:
            raise RuntimeError("Failed to persist outbound stock transaction")

        if self._cache is not None:
            self._cache.invalidate_prefix("inventory_products:")

        return OrderResponseDTO(
            id=saved_exit.id,
            order_type="outbound",
            sku_id=saved_exit.sku_id,
            sku_code=sku.sku,
            warehouse_id=saved_exit.warehouse_id,
            quantity=saved_exit.quantity,
            user_uuid=saved_exit.user_uuid,
            created_at=saved_exit.created_at,
        )

    def list_orders(self) -> List[Dict[str, Any]]:
        """List all inbound and outbound transactions sorted by date descending."""
        return self._repo.list_orders()


__all__ = ["InventoryService"]
