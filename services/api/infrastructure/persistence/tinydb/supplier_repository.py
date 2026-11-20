"""TinyDB persistence adapter for Suppliers domain.

Implements SupplierRepositoryPort using TinyDB document store.
"""

from datetime import datetime, timezone
from typing import Any, List, Optional
from tinydb import Query, TinyDB

from domain.suppliers.models import Supplier
from domain.suppliers.ports import SupplierRepositoryPort
from infrastructure.persistence.tinydb.client import get_table, get_tinydb


class TinyDBSupplierRepository(SupplierRepositoryPort):
    """TinyDB document store adapter implementing SupplierRepositoryPort."""

    def __init__(self, db: Optional[TinyDB] = None, table_name: str = "suppliers") -> None:
        """Initialize supplier repository with TinyDB table."""
        self._db = db if db is not None else get_tinydb()
        self.table = get_table(table_name, db=self._db)
        self.SupplierQuery = Query()

    def create(self, supplier: Supplier) -> Supplier:
        """Persist a new supplier entity and return saved instance with assigned doc_id as id."""
        data = supplier.model_dump(exclude={"id"})
        now_iso = datetime.now(timezone.utc).isoformat()
        if not data.get("created_at"):
            data["created_at"] = now_iso
        # updated_at is always stamped by system upon creation
        data["updated_at"] = now_iso

        doc_id = self.table.insert(data)
        data["id"] = doc_id
        return Supplier(**data)

    def get_by_id(self, supplier_id: int) -> Optional[Supplier]:
        """Retrieve supplier by doc_id."""
        doc = self.table.get(doc_id=supplier_id)
        if not doc:
            return None
        data = dict(doc)
        data["id"] = doc.doc_id
        return Supplier(**data)

    def list_all(
        self, country: Optional[str] = None, category: Optional[str] = None
    ) -> List[Supplier]:
        """List suppliers matching optional country and category filters."""
        query = None

        if country:
            country_norm = country.strip().lower()
            if country_norm in ("usa", "united states", "us"):
                query = self.SupplierQuery.country.test(
                    lambda c: bool(c and str(c).strip().lower() in ("usa", "united states", "us"))
                )
            else:
                query = self.SupplierQuery.country.test(
                    lambda c: bool(c and str(c).strip().lower() == country_norm)
                )

        if category:
            cat_norm = category.strip().lower()

            def _category_matches(cats: Any) -> bool:
                if isinstance(cats, list):
                    return any(bool(c and str(c).strip().lower() == cat_norm) for c in cats)
                elif isinstance(cats, str):
                    return str(cats).strip().lower() == cat_norm
                return False

            cat_query = self.SupplierQuery.categories.test(_category_matches) | self.SupplierQuery.category.test(
                lambda c: bool(c and str(c).strip().lower() == cat_norm)
            )

            if query is not None:
                query = query & cat_query
            else:
                query = cat_query

        if query is not None:
            results = self.table.search(query)
        else:
            results = self.table.all()

        suppliers: List[Supplier] = []
        for r in results:
            data = dict(r)
            data["id"] = r.doc_id
            suppliers.append(Supplier(**data))

        return suppliers

    def update_rate(self, supplier_id: int, rate: float) -> Optional[Supplier]:
        """Update shipping cost/rate for a supplier."""
        existing = self.table.get(doc_id=supplier_id)
        if not existing:
            return None

        now_str = datetime.now(timezone.utc).isoformat()
        self.table.update(
            {
                "rate_per_shipment": rate,
                "cost_per_kg": rate,
                "updated_at": now_str,
            },
            doc_ids=[supplier_id],
        )
        return self.get_by_id(supplier_id)

    def update_status(self, supplier_id: int, status: str) -> Optional[Supplier]:
        """Update operational status for a supplier."""
        existing = self.table.get(doc_id=supplier_id)
        if not existing:
            return None

        now_str = datetime.now(timezone.utc).isoformat()
        self.table.update(
            {"status": status, "updated_at": now_str},
            doc_ids=[supplier_id],
        )
        return self.get_by_id(supplier_id)

    def delete(self, supplier_id: int) -> bool:
        """Delete supplier record."""
        existing = self.table.get(doc_id=supplier_id)
        if not existing:
            return False

        removed = self.table.remove(doc_ids=[supplier_id])
        return len(removed) > 0


__all__ = ["TinyDBSupplierRepository"]
