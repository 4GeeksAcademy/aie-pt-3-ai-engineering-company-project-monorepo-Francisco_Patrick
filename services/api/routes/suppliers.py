from fastapi import APIRouter, HTTPException, Query
from tinydb import Query as TinyQuery
from datetime import datetime
from typing import List, Optional

from models import SupplierCreate, Supplier, SupplierUpdateRate, SupplierUpdateStatus
from infrastructure.database import get_db

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

def get_current_time_str() -> str:
    return datetime.utcnow().isoformat()

@router.post("", response_model=Supplier, status_code=201)
def create_supplier(supplier_in: SupplierCreate):
    db = get_db()
    table = db.table('suppliers')
    
    supplier_dict = supplier_in.model_dump()
    supplier_dict["updated_at"] = get_current_time_str()
    
    doc_id = table.insert(supplier_dict)
    supplier_dict["id"] = doc_id
    
    return supplier_dict

@router.get("", response_model=List[Supplier])
def list_suppliers(
    country: Optional[str] = Query(None, description="Filter by country"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    db = get_db()
    table = db.table('suppliers')
    
    SupplierQuery = TinyQuery()
    
    query = None
    if country:
        query = (SupplierQuery.country == country)
        
    if category:
        category_query = (SupplierQuery.categories.any(category))
        if query is not None:
            query = query & category_query
        else:
            query = category_query
            
    if query is not None:
        results = table.search(query)
    else:
        results = table.all()
        
    # Inject doc_id as id
    response = []
    for r in results:
        data = dict(r)
        data["id"] = r.doc_id
        response.append(data)
        
    return response

@router.get("/{id}", response_model=Supplier)
def get_supplier(id: int):
    db = get_db()
    table = db.table('suppliers')
    
    result = table.get(doc_id=id)
    if not result:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    data = dict(result)
    data["id"] = result.doc_id
    return data

@router.patch("/{id}/rate", response_model=Supplier)
def update_supplier_rate(id: int, update_data: SupplierUpdateRate):
    db = get_db()
    table = db.table('suppliers')
    
    result = table.get(doc_id=id)
    if not result:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    new_data = {"cost_per_kg": update_data.cost_per_kg, "updated_at": get_current_time_str()}
    table.update(new_data, doc_ids=[id])
    
    updated = table.get(doc_id=id)
    data = dict(updated)
    data["id"] = updated.doc_id
    return data

@router.patch("/{id}/status", response_model=Supplier)
def update_supplier_status(id: int, update_data: SupplierUpdateStatus):
    db = get_db()
    table = db.table('suppliers')
    
    result = table.get(doc_id=id)
    if not result:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    new_data = {"status": update_data.status, "updated_at": get_current_time_str()}
    table.update(new_data, doc_ids=[id])
    
    updated = table.get(doc_id=id)
    data = dict(updated)
    data["id"] = updated.doc_id
    return data

@router.delete("/{id}", status_code=204)
def delete_supplier(id: int):
    db = get_db()
    table = db.table('suppliers')
    
    result = table.get(doc_id=id)
    if not result:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    table.remove(doc_ids=[id])
    return
