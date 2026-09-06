import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database import get_db
from models import SupplierStatus
from datetime import datetime, timezone

def get_current_time():
    return datetime.now(timezone.utc).isoformat()

def seed():
    db = get_db()
    table = db.table("suppliers")
    
    seed_data = [
        {"name": "UPS", "country": "United States", "categories": ["standard", "express"], "cost_per_kg": 5.50, "status": SupplierStatus.active.value},
        {"name": "FedEx", "country": "United States", "categories": ["express", "overnight"], "cost_per_kg": 6.20, "status": SupplierStatus.active.value},
        {"name": "DHL US", "country": "United States", "categories": ["international"], "cost_per_kg": 8.00, "status": SupplierStatus.active.value},
        {"name": "DHL ES", "country": "Spain", "categories": ["international", "express"], "cost_per_kg": 7.50, "status": SupplierStatus.active.value},
        {"name": "MRW", "country": "Spain", "categories": ["standard", "express"], "cost_per_kg": 4.50, "status": SupplierStatus.active.value},
        {"name": "SEUR", "country": "Spain", "categories": ["standard"], "cost_per_kg": 4.20, "status": SupplierStatus.active.value},
        {"name": "US Local Courier", "country": "United States", "categories": ["standard"], "cost_per_kg": 3.50, "status": SupplierStatus.active.value},
        {"name": "ES Local Courier", "country": "Spain", "categories": ["standard"], "cost_per_kg": 3.20, "status": SupplierStatus.active.value},
    ]
    
    existing = table.all()
    existing_names = [s.get("name") for s in existing]
    
    inserted = 0
    for data in seed_data:
        if data["name"] not in existing_names:
            data["updated_at"] = get_current_time()
            table.insert(data)
            inserted += 1
            
    print(f"Inserted {inserted} new suppliers.")

if __name__ == "__main__":
    seed()
