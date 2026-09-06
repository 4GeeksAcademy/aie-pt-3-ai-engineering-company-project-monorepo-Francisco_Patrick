from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional
from tinydb import Query as DBQuery
from datetime import datetime, timezone

from models import SupplierCreate, SupplierInDB, SupplierUpdateRate, SupplierUpdateStatus
from database import get_db

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])

def get_current_time():
    return datetime.now(timezone.utc).isoformat()

@router.post("/", response_model=SupplierInDB, status_code=201)
def create_supplier(supplier: SupplierCreate):
    db = get_db()
    table = db.table("suppliers")
    
    supplier_dict = supplier.model_dump()
    supplier_dict["updated_at"] = get_current_time()
    
    supplier_id = table.insert(supplier_dict)
    
    return {**supplier_dict, "id": supplier_id}

@router.get("/", response_model=List[SupplierInDB])
def list_suppliers(
    country: Optional[str] = None,
    category: Optional[str] = None
):
    db = get_db()
    table = db.table("suppliers")
    results = table.all()
    
    filtered_results = []
    for r in results:
        match = True
        if country and r.get("country").lower() != country.lower():
            match = False
        if category and category.lower() not in [c.lower() for c in r.get("categories", [])]:
            match = False
        if match:
            filtered_results.append({**r, "id": r.doc_id})
            
    return filtered_results

@router.get("/{id}", response_model=SupplierInDB)
def get_supplier(id: int):
    db = get_db()
    table = db.table("suppliers")
    
    supplier = table.get(doc_id=id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    return {**supplier, "id": supplier.doc_id}

@router.patch("/{id}/rate", response_model=SupplierInDB)
def update_supplier_rate(id: int, update: SupplierUpdateRate):
    db = get_db()
    table = db.table("suppliers")
    
    supplier = table.get(doc_id=id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    table.update({"cost_per_kg": update.cost_per_kg, "updated_at": get_current_time()}, doc_ids=[id])
    
    updated_supplier = table.get(doc_id=id)
    return {**updated_supplier, "id": updated_supplier.doc_id}

@router.patch("/{id}/status", response_model=SupplierInDB)
def update_supplier_status(id: int, update: SupplierUpdateStatus):
    db = get_db()
    table = db.table("suppliers")
    
    supplier = table.get(doc_id=id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    table.update({"status": update.status.value, "updated_at": get_current_time()}, doc_ids=[id])
    
    updated_supplier = table.get(doc_id=id)
    return {**updated_supplier, "id": updated_supplier.doc_id}

@router.delete("/{id}", status_code=204)
def delete_supplier(id: int):
    db = get_db()
    table = db.table("suppliers")
    
    supplier = table.get(doc_id=id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    table.remove(doc_ids=[id])
    return None
