from fastapi import APIRouter, HTTPException, Query
from tinydb import Query as TinyQuery
from datetime import datetime
from typing import List, Optional

from domain.models import SupplierCreate, Supplier, SupplierUpdateRate, SupplierUpdateStatus, User
from infrastructure.database import get_tinydb
from presentation.dependencies import get_current_user
from fastapi import Depends

router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"],
    dependencies=[Depends(get_current_user)]
)

def get_current_time_str() -> str:
    return datetime.utcnow().isoformat()

@router.post("", response_model=Supplier, status_code=201)
def create_supplier(supplier_in: SupplierCreate):
    try:
        db = get_tinydb()
        table = db.table('suppliers')
        
        supplier_dict = supplier_in.model_dump()
        supplier_dict["updated_at"] = get_current_time_str()
        
        doc_id = table.insert(supplier_dict)
        supplier_dict["id"] = doc_id
        
        return supplier_dict
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Failed to create supplier due to a database error.")

@router.get("", response_model=List[Supplier])
def list_suppliers(
    country: Optional[str] = Query(None, description="Filter by country"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    try:
        db = get_tinydb()
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
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Failed to retrieve suppliers due to a database query error.")

@router.get("/{id}", response_model=Supplier)
def get_supplier(id: int):
    try:
        db = get_tinydb()
        table = db.table('suppliers')
        
        result = table.get(doc_id=id)
        if not result:
            raise HTTPException(status_code=404, detail="Supplier not found")
            
        data = dict(result)
        data["id"] = result.doc_id
        return data
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Failed to retrieve supplier details.")

@router.patch("/{id}/rate", response_model=Supplier)
def update_supplier_rate(id: int, update_data: SupplierUpdateRate):
    try:
        db = get_tinydb()
        table = db.table('suppliers')
        
        result = table.get(doc_id=id)
        if not result:
            raise HTTPException(status_code=404, detail="Supplier not found")
            
        new_data = {"cost_per_kg": update_data.cost_per_kg, "updated_at": get_current_time_str()}
        table.update(new_data, doc_ids=[id])
        
        updated = table.get(doc_id=id)
        if not updated:
            raise HTTPException(status_code=404, detail="Supplier not found after update")
        data = dict(updated)
        data["id"] = updated.doc_id
        return data
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Failed to update supplier rate.")

@router.patch("/{id}/status", response_model=Supplier)
def update_supplier_status(id: int, update_data: SupplierUpdateStatus):
    try:
        db = get_tinydb()
        table = db.table('suppliers')
        
        result = table.get(doc_id=id)
        if not result:
            raise HTTPException(status_code=404, detail="Supplier not found")
            
        new_data = {"status": update_data.status, "updated_at": get_current_time_str()}
        table.update(new_data, doc_ids=[id])
        
        updated = table.get(doc_id=id)
        if not updated:
            raise HTTPException(status_code=404, detail="Supplier not found after update")
        data = dict(updated)
        data["id"] = updated.doc_id
        return data
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Failed to update supplier status.")

@router.delete("/{id}", status_code=204)
def delete_supplier(id: int):
    try:
        db = get_tinydb()
        table = db.table('suppliers')
        
        result = table.get(doc_id=id)
        if not result:
            raise HTTPException(status_code=404, detail="Supplier not found")
            
        table.remove(doc_ids=[id])
        return
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Failed to delete supplier.")
