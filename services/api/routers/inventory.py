from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from infrastructure.database import get_db
from presentation.dependencies import get_current_user
from domain.models import User
from models import SKU
from schemas import (
    ProductCreate,
    ProductResponse,
    InboundOrderCreate,
    OutboundOrderCreate,
    OrderResponse
)
from application.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def compute_sku_stock(session: Session, sku_id: int, warehouse_id: str) -> int:
    """Calculates current_stock as SUM(inbound) - SUM(outbound) for a given SKU and warehouse."""
    return InventoryService.calculate_stock(session, sku_id, warehouse_id)


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a new product SKU in Supabase (requires authentication). Initial stock is 0."""
    existing_sku = session.exec(select(SKU).where(SKU.sku == product_in.sku)).first()
    if existing_sku:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product SKU '{product_in.sku}' already exists"
        )

    sku_obj = SKU(
        sku=product_in.sku,
        name=product_in.name,
        warehouse_id=product_in.warehouse_id,
        low_stock_threshold=product_in.low_stock_threshold
    )
    session.add(sku_obj)
    session.commit()
    session.refresh(sku_obj)

    stock = compute_sku_stock(session, sku_obj.id, sku_obj.warehouse_id)

    return ProductResponse(
        id=sku_obj.id,
        sku=sku_obj.sku,
        name=sku_obj.name,
        warehouse_id=sku_obj.warehouse_id,
        low_stock_threshold=sku_obj.low_stock_threshold,
        current_stock=stock,
        created_at=sku_obj.created_at
    )


@router.get("/products", response_model=List[ProductResponse])
def list_products(session: Session = Depends(get_db)):
    """Lists all products with calculated current_stock."""
    skus = session.exec(select(SKU)).all()
    results = []
    for s in skus:
        stock = compute_sku_stock(session, s.id, s.warehouse_id)
        results.append(
            ProductResponse(
                id=s.id,
                sku=s.sku,
                name=s.name,
                warehouse_id=s.warehouse_id,
                low_stock_threshold=s.low_stock_threshold,
                current_stock=stock,
                created_at=s.created_at
            )
        )
    return results


@router.get("/products/{id}", response_model=ProductResponse)
def get_product(id: int, session: Session = Depends(get_db)):
    """Gets a product by ID with its calculated current_stock."""
    sku_obj = session.get(SKU, id)
    if not sku_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {id} not found"
        )
    
    stock = compute_sku_stock(session, sku_obj.id, sku_obj.warehouse_id)
    return ProductResponse(
        id=sku_obj.id,
        sku=sku_obj.sku,
        name=sku_obj.name,
        warehouse_id=sku_obj.warehouse_id,
        low_stock_threshold=sku_obj.low_stock_threshold,
        current_stock=stock,
        created_at=sku_obj.created_at
    )


@router.post("/orders/inbound", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_inbound_order(
    order_in: InboundOrderCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Registers an inbound order (StockEntry), incrementing derived inventory stock."""
    sku_obj = InventoryService.get_sku_by_id(session, order_in.sku_id)
    if not sku_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {order_in.sku_id} not found"
        )

    entry = InventoryService.create_inbound_order(session, order_in, current_user.id)

    return OrderResponse(
        id=entry.id,
        order_type="inbound",
        sku_id=entry.sku_id,
        sku_code=sku_obj.sku,
        warehouse_id=entry.warehouse_id,
        quantity=entry.quantity,
        user_uuid=entry.user_uuid,
        created_at=entry.created_at
    )


@router.post("/orders/outbound", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_outbound_order(
    order_in: OutboundOrderCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Registers an outbound order (StockExit), reducing derived inventory stock."""
    sku_obj = InventoryService.get_sku_by_id(session, order_in.sku_id)
    if not sku_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {order_in.sku_id} not found"
        )

    is_valid, current_stock = InventoryService.validate_outbound_stock(
        session,
        order_in.sku_id,
        order_in.warehouse_id,
        order_in.quantity
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock for SKU '{sku_obj.sku}' in warehouse '{order_in.warehouse_id}'. Requested: {order_in.quantity}, Available: {current_stock}"
        )

    exit_rec = InventoryService.create_outbound_order(session, order_in, current_user.id)

    return OrderResponse(
        id=exit_rec.id,
        order_type="outbound",
        sku_id=exit_rec.sku_id,
        sku_code=sku_obj.sku,
        warehouse_id=exit_rec.warehouse_id,
        quantity=exit_rec.quantity,
        user_uuid=exit_rec.user_uuid,
        created_at=exit_rec.created_at
    )



@router.get("/orders", response_model=List[OrderResponse])
def list_orders(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all inbound and outbound inventory orders."""
    return InventoryService.list_orders(session)

