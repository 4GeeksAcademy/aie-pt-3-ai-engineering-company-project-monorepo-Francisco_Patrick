"""Inventory API router (canonical v1, also mounted at the legacy /inventory prefix)."""

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
from infrastructure.queue.schemas import AsyncTaskAcceptedResponse
from presentation.dependencies import get_current_user, get_inventory_service_dep

router = APIRouter(tags=["Inventory"])

# The legacy contract never exposed this derived flag; keep responses identical.
_LEGACY_PRODUCT_EXCLUDE = {"is_low_stock"}


@router.post(
    "/products",
    response_model=ProductResponseDTO,
    response_model_exclude=_LEGACY_PRODUCT_EXCLUDE,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    product_in: ProductCreateDTO,
    service: InventoryService = Depends(get_inventory_service_dep),
    current_user: User = Depends(get_current_user),
) -> InventoryProduct:
    """Create a product SKU (requires authentication). Initial stock is 0."""
    try:
        return service.create_product(product_in)
    except DuplicateEntityError:
        # Legacy contract: duplicate SKU is a 400, not the global 409 mapping.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product SKU '{product_in.sku}' already exists",
        )


@router.get(
    "/products",
    response_model=AsyncTaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="List all products asynchronously",
    description="Enqueues inventory stock aggregation task and returns tracking ID.",
)
def list_products(
    response: Response,
    include_archived: bool = Query(default=False, description="Include archived products"),
) -> AsyncTaskAcceptedResponse:
    """Enqueues inventory stock aggregation task and returns tracking ID."""
    from infrastructure.queue.celery_app import register_enqueued_task
    from infrastructure.queue.tasks import list_products_task

    async_result = list_products_task.delay(include_archived=include_archived)
    task_id = str(async_result.id)
    register_enqueued_task(task_id, "inventory.list_products")
    poll_url = f"/api/v1/tasks/{task_id}"
    response.headers["Location"] = poll_url

    return AsyncTaskAcceptedResponse(
        task_id=task_id,
        status="pending",
        message="Inventory stock aggregation task enqueued.",
        poll_url=poll_url,
    )



@router.get(
    "/products/{id}",
    response_model=ProductResponseDTO,
    response_model_exclude=_LEGACY_PRODUCT_EXCLUDE,
)
def get_product(
    id: int,
    service: InventoryService = Depends(get_inventory_service_dep),
) -> InventoryProduct:
    """Return a product by ID with calculated stock (404 when missing)."""
    return service.get_product_by_id(id)


@router.post(
    "/orders/inbound",
    response_model=OrderResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_inbound_order(
    order_in: InboundOrderCreateDTO,
    service: InventoryService = Depends(get_inventory_service_dep),
    current_user: User = Depends(get_current_user),
) -> OrderResponseDTO:
    """Register an inbound order, increasing derived stock."""
    return service.create_inbound_order(order_in, current_user.id)


@router.post(
    "/orders/outbound",
    response_model=OrderResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_outbound_order(
    order_in: OutboundOrderCreateDTO,
    service: InventoryService = Depends(get_inventory_service_dep),
    current_user: User = Depends(get_current_user),
) -> OrderResponseDTO:
    """Register an outbound order, rejecting it when stock is insufficient."""
    return service.create_outbound_order(order_in, current_user.id)


@router.get("/orders", response_model=List[OrderResponseDTO])
def list_orders(
    service: InventoryService = Depends(get_inventory_service_dep),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all inbound and outbound inventory orders."""
    return service.list_orders()
