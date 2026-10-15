"""Suppliers API router (canonical v1, also mounted at the legacy /suppliers prefix)."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from application.suppliers.dto import (
    SupplierCreateDTO,
    SupplierUpdateRateDTO,
    SupplierUpdateStatusDTO,
)
from application.suppliers.supplier_service import SupplierService
from domain.suppliers.models import Supplier
from presentation.dependencies import get_current_user, get_supplier_service_dep

router = APIRouter(tags=["Suppliers"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=Supplier, status_code=201)
def create_supplier(
    supplier_in: SupplierCreateDTO,
    service: SupplierService = Depends(get_supplier_service_dep),
) -> Supplier:
    """Create a supplier and return the persisted entity."""
    return service.create_supplier(supplier_in)


@router.get("", response_model=List[Supplier])
def list_suppliers(
    country: Optional[str] = Query(None, description="Filter by country"),
    category: Optional[str] = Query(None, description="Filter by category"),
    service: SupplierService = Depends(get_supplier_service_dep),
) -> List[Supplier]:
    """List suppliers, optionally filtered by country and category."""
    return service.list_suppliers(country=country, category=category)


@router.get("/{id}", response_model=Supplier)
def get_supplier(
    id: int,
    service: SupplierService = Depends(get_supplier_service_dep),
) -> Supplier:
    """Return a supplier by numeric identifier (404 when missing)."""
    return service.get_supplier_by_id(id)


@router.patch("/{id}/rate", response_model=Supplier)
def update_supplier_rate(
    id: int,
    update_data: SupplierUpdateRateDTO,
    service: SupplierService = Depends(get_supplier_service_dep),
) -> Supplier:
    """Update a supplier's freight rate per kg."""
    return service.update_supplier_rate(id, update_data.cost_per_kg)


@router.patch("/{id}/status", response_model=Supplier)
def update_supplier_status(
    id: int,
    update_data: SupplierUpdateStatusDTO,
    service: SupplierService = Depends(get_supplier_service_dep),
) -> Supplier:
    """Update a supplier's operational status."""
    return service.update_supplier_status(id, update_data.status)


@router.delete("/{id}", status_code=204)
def delete_supplier(
    id: int,
    service: SupplierService = Depends(get_supplier_service_dep),
) -> None:
    """Delete a supplier (404 when missing)."""
    service.delete_supplier(id)
