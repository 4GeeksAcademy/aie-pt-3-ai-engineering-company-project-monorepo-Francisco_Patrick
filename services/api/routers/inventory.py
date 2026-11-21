"""Inventory API router under prefix /inventory.

Implements all inventory endpoints adhering strictly to trackflow-BRIEFING.es.md.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from application.inventory.dto import (
    InboundOrderCreateDTO,
    OrderResponseDTO,
    OutboundOrderCreateDTO,
    ProductCreateDTO,
    ProductResponseDTO,
)
from application.inventory.inventory_service import InventoryService
from domain.common.exceptions import DuplicateEntityError
from domain.inventory.models import InventoryProduct
from domain.models import User
from presentation.dependencies import get_current_user, get_inventory_service_dep

router = APIRouter(prefix="/inventory", tags=["Inventory"])

_LEGACY_PRODUCT_EXCLUDE = {"is_low_stock"}


@router.get(
    "/products",
    response_model=List[ProductResponseDTO],
    response_model_exclude=_LEGACY_PRODUCT_EXCLUDE,
    status_code=status.HTTP_200_OK,
    summary="List all products with current stock",
)
def list_products(
    service: InventoryService = Depends(get_inventory_service_dep),
) -> List[InventoryProduct]:
    """List all products with dynamically calculated net stock levels."""
    return service.list_products()


@router.post(
    "/products",
    response_model=ProductResponseDTO,
    response_model_exclude=_LEGACY_PRODUCT_EXCLUDE,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product SKU",
)
def create_product(
    product_in: ProductCreateDTO,
    service: InventoryService = Depends(get_inventory_service_dep),
    current_user: User = Depends(get_current_user),
) -> InventoryProduct:
    """Create a new product SKU (requires authentication). Initial stock is 0."""
    try:
        return service.create_product(product_in)
    except DuplicateEntityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product SKU '{product_in.sku}' already exists",
        )


@router.get(
    "/products/{id}",
    response_model=ProductResponseDTO,
    response_model_exclude=_LEGACY_PRODUCT_EXCLUDE,
    summary="Get product detail by ID",
)
def get_product(
    id: int,
    service: InventoryService = Depends(get_inventory_service_dep),
) -> InventoryProduct:
    """Return a product by ID with calculated stock."""
    return service.get_product_by_id(id)


@router.post(
    "/orders/inbound",
    response_model=OrderResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Register an inbound stock entry",
)
def create_inbound_order(
    order_in: InboundOrderCreateDTO,
    service: InventoryService = Depends(get_inventory_service_dep),
    current_user: User = Depends(get_current_user),
) -> OrderResponseDTO:
    """Register an inbound order, increasing derived stock and binding user_uuid."""
    return service.create_inbound_order(order_in, current_user.id)


@router.post(
    "/orders/outbound",
    response_model=OrderResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Register an outbound stock exit",
)
def create_outbound_order(
    order_in: OutboundOrderCreateDTO,
    service: InventoryService = Depends(get_inventory_service_dep),
    current_user: User = Depends(get_current_user),
) -> OrderResponseDTO:
    """Register an outbound order, rejecting when stock is insufficient and binding user_uuid."""
    return service.create_outbound_order(order_in, current_user.id)


@router.get(
    "/orders",
    response_model=List[OrderResponseDTO],
    summary="List all stock movements",
)
def list_orders(
    service: InventoryService = Depends(get_inventory_service_dep),
    current_user: Optional[User] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all inbound and outbound inventory orders with SKU data and user_uuid."""
    return service.list_orders()


__all__ = ["router"]
