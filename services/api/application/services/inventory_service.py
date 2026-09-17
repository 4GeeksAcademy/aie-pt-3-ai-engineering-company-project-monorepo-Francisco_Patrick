from typing import List, Dict, Any
from sqlmodel import Session, select, func
from models import SKU, StockEntry, StockExit
from schemas import InboundOrderCreate, OutboundOrderCreate, OrderResponse


class InventoryService:
    """Service handling inventory stock calculation and order transactions."""

    @staticmethod
    def calculate_stock(session: Session, sku_id: int, warehouse_id: str) -> int:
        """
        Calculates current stock as SUM(inbound) - SUM(outbound) for a given SKU and warehouse scope.
        Returns 0 if no entries/exits exist.
        """
        inbound_qty = session.exec(
            select(func.coalesce(func.sum(StockEntry.quantity), 0))
            .where(StockEntry.sku_id == sku_id)
            .where(StockEntry.warehouse_id == warehouse_id)
        ).one()

        outbound_qty = session.exec(
            select(func.coalesce(func.sum(StockExit.quantity), 0))
            .where(StockExit.sku_id == sku_id)
            .where(StockExit.warehouse_id == warehouse_id)
        ).one()

        return int(inbound_qty) - int(outbound_qty)

    @staticmethod
    def validate_outbound_stock(
        session: Session,
        sku_id: int,
        warehouse_id: str,
        requested_quantity: int
    ) -> tuple[bool, int]:
        """
        Validates whether sufficient stock exists for an outbound order in a given warehouse.
        Returns (is_valid, current_stock).
        """
        current_stock = InventoryService.calculate_stock(session, sku_id, warehouse_id)
        if current_stock < requested_quantity:
            return False, current_stock
        return True, current_stock

    @staticmethod
    def get_sku_by_id(session: Session, sku_id: int) -> SKU | None:
        """Retrieves a SKU by its primary key ID."""
        return session.get(SKU, sku_id)


    @staticmethod
    def create_inbound_order(
        session: Session,
        order_in: InboundOrderCreate,
        user_uuid: str
    ) -> StockEntry:
        """Creates and persists an Inbound StockEntry record."""
        entry = StockEntry(
            sku_id=order_in.sku_id,
            warehouse_id=order_in.warehouse_id,
            quantity=order_in.quantity,
            user_uuid=user_uuid
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    @staticmethod
    def create_outbound_order(
        session: Session,
        order_in: OutboundOrderCreate,
        user_uuid: str
    ) -> StockExit:
        """Creates and persists an Outbound StockExit record."""
        exit_rec = StockExit(
            sku_id=order_in.sku_id,
            warehouse_id=order_in.warehouse_id,
            quantity=order_in.quantity,
            user_uuid=user_uuid
        )
        session.add(exit_rec)
        session.commit()
        session.refresh(exit_rec)
        return exit_rec

    @staticmethod
    def list_orders(session: Session) -> List[Dict[str, Any]]:
        """
        Lists all inbound and outbound transactions joined with SKU codes,
        sorted by creation date descending.
        """
        inbound_entries = session.exec(select(StockEntry)).all()
        outbound_exits = session.exec(select(StockExit)).all()

        skus = {sku.id: sku.sku for sku in session.exec(select(SKU)).all() if sku.id is not None}

        orders: List[Dict[str, Any]] = []

        for entry in inbound_entries:
            orders.append({
                "id": entry.id,
                "order_type": "inbound",
                "sku_id": entry.sku_id,
                "sku_code": skus.get(entry.sku_id, "UNKNOWN"),
                "warehouse_id": entry.warehouse_id,
                "quantity": entry.quantity,
                "user_uuid": entry.user_uuid,
                "created_at": entry.created_at
            })

        for exit_rec in outbound_exits:
            orders.append({
                "id": exit_rec.id,
                "order_type": "outbound",
                "sku_id": exit_rec.sku_id,
                "sku_code": skus.get(exit_rec.sku_id, "UNKNOWN"),
                "warehouse_id": exit_rec.warehouse_id,
                "quantity": exit_rec.quantity,
                "user_uuid": exit_rec.user_uuid,
                "created_at": exit_rec.created_at
            })

        orders.sort(key=lambda x: x["created_at"], reverse=True)
        return orders
