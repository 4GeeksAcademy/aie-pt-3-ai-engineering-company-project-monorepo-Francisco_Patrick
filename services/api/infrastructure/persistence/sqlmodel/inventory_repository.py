"""SQLModel persistence adapter for Inventory domain.

Implements InventoryRepositoryPort using SQLModel / SQLAlchemy relational sessions.
Maps between pure domain models and ORM table records.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from domain.inventory.models import (
    SKU as DomainSKU,
    InventoryProduct,
    StockEntry as DomainStockEntry,
    StockExit as DomainStockExit,
)
from domain.inventory.ports import InventoryRepositoryPort
from infrastructure.persistence.sqlmodel.client import sqlmodel_manager
from infrastructure.persistence.sqlmodel.models import (
    SKU as ORMSKU,
    StockEntry as ORMStockEntry,
    StockExit as ORMStockExit,
)


class SQLModelInventoryRepository(InventoryRepositoryPort):
    """Relational SQLModel persistence adapter implementing InventoryRepositoryPort."""

    def __init__(self, session: Optional[Session] = None) -> None:
        """Initialize adapter with an optional active Session.

        Args:
            session: Optional existing SQLModel Session.
        """
        self._session = session

    @contextmanager
    def _get_session(self) -> Generator[Session, None, None]:
        """Context manager yielding active session or creating transient session."""
        if self._session is not None:
            yield self._session
        else:
            eng = sqlmodel_manager.get_engine()
            with Session(eng) as session:
                yield session

    def create_sku(self, sku: DomainSKU) -> DomainSKU:
        """Create and persist a new SKU in the relational catalog."""
        with self._get_session() as session:
            orm_sku = ORMSKU(
                sku=sku.sku,
                name=sku.name,
                client_name=sku.client_name,
                category=sku.category,
                warehouse=sku.warehouse,
                warehouse_id=sku.warehouse_id,
                low_stock_threshold=sku.low_stock_threshold,
            )
            session.add(orm_sku)
            session.commit()
            session.refresh(orm_sku)

            return DomainSKU(
                id=orm_sku.id,
                sku=orm_sku.sku,
                name=orm_sku.name,
                client_name=orm_sku.client_name,
                category=orm_sku.category,
                warehouse=orm_sku.warehouse,
                warehouse_id=orm_sku.warehouse_id,
                low_stock_threshold=orm_sku.low_stock_threshold,
                created_at=orm_sku.created_at,
            )

    def get_sku_by_id(self, sku_id: int) -> Optional[DomainSKU]:
        """Retrieve an SKU by primary key."""
        with self._get_session() as session:
            orm_sku = session.get(ORMSKU, sku_id)
            if not orm_sku:
                return None
            return DomainSKU(
                id=orm_sku.id,
                sku=orm_sku.sku,
                name=orm_sku.name,
                client_name=orm_sku.client_name,
                category=orm_sku.category,
                warehouse=orm_sku.warehouse,
                warehouse_id=orm_sku.warehouse_id,
                low_stock_threshold=orm_sku.low_stock_threshold,
                created_at=orm_sku.created_at,
            )

    def get_sku_by_code(self, sku_code: str) -> Optional[DomainSKU]:
        """Retrieve an SKU by alphanumeric code."""
        with self._get_session() as session:
            orm_sku = session.exec(select(ORMSKU).where(ORMSKU.sku == sku_code)).first()
            if not orm_sku:
                return None
            return DomainSKU(
                id=orm_sku.id,
                sku=orm_sku.sku,
                name=orm_sku.name,
                client_name=orm_sku.client_name,
                category=orm_sku.category,
                warehouse=orm_sku.warehouse,
                warehouse_id=orm_sku.warehouse_id,
                low_stock_threshold=orm_sku.low_stock_threshold,
                created_at=orm_sku.created_at,
            )

    def calculate_stock(self, sku_id: int, warehouse_id: str) -> int:
        """Calculate current net stock as SUM(inbound) - SUM(outbound) for SKU and warehouse."""
        with self._get_session() as session:
            wh_cond_entry = (ORMStockEntry.warehouse == warehouse_id) | (
                ORMStockEntry.warehouse_id == warehouse_id
            )
            wh_cond_exit = (ORMStockExit.warehouse == warehouse_id) | (
                ORMStockExit.warehouse_id == warehouse_id
            )

            inbound_qty = session.exec(
                select(func.coalesce(func.sum(ORMStockEntry.quantity), 0))
                .where(ORMStockEntry.sku_id == sku_id)
                .where(wh_cond_entry)
            ).one()

            outbound_qty = session.exec(
                select(func.coalesce(func.sum(ORMStockExit.quantity), 0))
                .where(ORMStockExit.sku_id == sku_id)
                .where(wh_cond_exit)
            ).one()

            return int(inbound_qty) - int(outbound_qty)

    def list_all_products(self) -> List[InventoryProduct]:
        """Retrieve all products with dynamic net stock."""
        with self._get_session() as session:
            skus = session.exec(select(ORMSKU)).all()
            products: List[InventoryProduct] = []

            for s in skus:
                if s.id is None:
                    continue
                wh = getattr(s, "warehouse", s.warehouse_id)
                stock = self.calculate_stock(s.id, wh)
                products.append(
                    InventoryProduct(
                        id=s.id,
                        sku=s.sku,
                        name=s.name,
                        client_name=getattr(s, "client_name", "PureStep Footwear"),
                        category=getattr(s, "category", "fashion"),
                        warehouse=wh,
                        warehouse_id=s.warehouse_id,
                        current_stock=stock,
                        low_stock_threshold=s.low_stock_threshold,
                        is_low_stock=stock <= s.low_stock_threshold,
                        created_at=s.created_at,
                    )
                )
            return products

    def get_product_by_id(self, sku_id: int) -> Optional[InventoryProduct]:
        """Retrieve a single product projection by SKU id."""
        with self._get_session() as session:
            orm_sku = session.get(ORMSKU, sku_id)
            if not orm_sku or orm_sku.id is None:
                return None
            wh = getattr(orm_sku, "warehouse", orm_sku.warehouse_id)
            stock = self.calculate_stock(orm_sku.id, wh)
            return InventoryProduct(
                id=orm_sku.id,
                sku=orm_sku.sku,
                name=orm_sku.name,
                client_name=getattr(orm_sku, "client_name", "PureStep Footwear"),
                category=getattr(orm_sku, "category", "fashion"),
                warehouse=wh,
                warehouse_id=orm_sku.warehouse_id,
                current_stock=stock,
                low_stock_threshold=orm_sku.low_stock_threshold,
                is_low_stock=stock <= orm_sku.low_stock_threshold,
                created_at=orm_sku.created_at,
            )

    def add_inbound_entry(self, entry: DomainStockEntry) -> DomainStockEntry:
        """Persist an inbound stock transaction."""
        with self._get_session() as session:
            orm_entry = ORMStockEntry(
                sku_id=entry.sku_id,
                warehouse=entry.warehouse,
                warehouse_id=entry.warehouse_id,
                quantity=entry.quantity,
                reference=entry.reference,
                user_uuid=entry.user_uuid,
            )
            session.add(orm_entry)
            session.commit()
            session.refresh(orm_entry)

            return DomainStockEntry(
                id=orm_entry.id,
                sku_id=orm_entry.sku_id,
                warehouse=orm_entry.warehouse,
                warehouse_id=orm_entry.warehouse_id,
                quantity=orm_entry.quantity,
                reference=orm_entry.reference,
                user_uuid=orm_entry.user_uuid,
                created_at=orm_entry.created_at,
            )

    def add_outbound_exit(self, exit_rec: DomainStockExit) -> DomainStockExit:
        """Persist an outbound stock transaction."""
        with self._get_session() as session:
            orm_exit = ORMStockExit(
                sku_id=exit_rec.sku_id,
                warehouse=exit_rec.warehouse,
                warehouse_id=exit_rec.warehouse_id,
                quantity=exit_rec.quantity,
                exit_type=exit_rec.exit_type,
                tracking_number=exit_rec.tracking_number,
                user_uuid=exit_rec.user_uuid,
            )
            session.add(orm_exit)
            session.commit()
            session.refresh(orm_exit)

            return DomainStockExit(
                id=orm_exit.id,
                sku_id=orm_exit.sku_id,
                warehouse=orm_exit.warehouse,
                warehouse_id=orm_exit.warehouse_id,
                quantity=orm_exit.quantity,
                exit_type=orm_exit.exit_type,
                tracking_number=orm_exit.tracking_number,
                user_uuid=orm_exit.user_uuid,
                created_at=orm_exit.created_at,
            )

    def list_orders(self) -> List[Dict[str, Any]]:
        """List joined chronological order records using eager loading (selectinload) to prevent N+1."""
        with self._get_session() as session:
            inbound_entries = session.exec(
                select(ORMStockEntry).options(selectinload(ORMStockEntry.sku))
            ).all()
            outbound_exits = session.exec(
                select(ORMStockExit).options(selectinload(ORMStockExit.sku))
            ).all()

            orders: List[Dict[str, Any]] = []

            for entry in inbound_entries:
                sku_code = entry.sku.sku if entry.sku else "UNKNOWN"
                orders.append(
                    {
                        "id": entry.id,
                        "order_type": "inbound",
                        "sku_id": entry.sku_id,
                        "sku_code": sku_code,
                        "reference": getattr(entry, "reference", ""),
                        "warehouse": getattr(entry, "warehouse", entry.warehouse_id),
                        "warehouse_id": entry.warehouse_id,
                        "quantity": entry.quantity,
                        "exit_type": None,
                        "tracking_number": None,
                        "user_uuid": entry.user_uuid,
                        "created_at": entry.created_at,
                    }
                )

            for exit_rec in outbound_exits:
                sku_code = exit_rec.sku.sku if exit_rec.sku else "UNKNOWN"
                orders.append(
                    {
                        "id": exit_rec.id,
                        "order_type": "outbound",
                        "sku_id": exit_rec.sku_id,
                        "sku_code": sku_code,
                        "reference": None,
                        "warehouse": getattr(exit_rec, "warehouse", exit_rec.warehouse_id),
                        "warehouse_id": exit_rec.warehouse_id,
                        "quantity": exit_rec.quantity,
                        "exit_type": getattr(exit_rec, "exit_type", "dispatch"),
                        "tracking_number": getattr(exit_rec, "tracking_number", None),
                        "user_uuid": exit_rec.user_uuid,
                        "created_at": exit_rec.created_at,
                    }
                )

            orders.sort(
                key=lambda x: x["created_at"] or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            return orders


__all__ = ["SQLModelInventoryRepository"]
