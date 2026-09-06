import sys
import os
from tinydb import TinyDB, Query
from datetime import datetime

# Import database module assuming we run this from services/api
sys.path.insert(0, os.path.dirname(__file__))
from database import get_db

INITIAL_SUPPLIERS = [
    {
        "name": "UPS",
        "country": "United States",
        "categories": ["express", "standard", "heavy"],
        "cost_per_kg": 5.50,
        "status": "active"
    },
    {
        "name": "FedEx",
        "country": "United States",
        "categories": ["express", "overnight"],
        "cost_per_kg": 6.20,
        "status": "active"
    },
    {
        "name": "DHL",
        "country": "United States",
        "categories": ["international", "express"],
        "cost_per_kg": 7.00,
        "status": "active"
    },
    {
        "name": "MRW",
        "country": "Spain",
        "categories": ["express", "national"],
        "cost_per_kg": 3.80,
        "status": "active"
    },
    {
        "name": "SEUR",
        "country": "Spain",
        "categories": ["standard", "heavy"],
        "cost_per_kg": 4.10,
        "status": "active"
    },
    {
        "name": "DHL Spain",
        "country": "Spain",
        "categories": ["international"],
        "cost_per_kg": 6.50,
        "status": "suspended"
    }
]

def get_current_time_str() -> str:
    return datetime.utcnow().isoformat()

def run_seed():
    db = get_db()
    table = db.table('suppliers')
    SupplierQuery = Query()
    
    inserted_count = 0
    for s in INITIAL_SUPPLIERS:
        # Check for duplicate by name and country
        exists = table.search((SupplierQuery.name == s["name"]) & (SupplierQuery.country == s["country"]))
        if not exists:
            s["updated_at"] = get_current_time_str()
            table.insert(s)
            inserted_count += 1
            
    print(f"Seeder executed successfully. Inserted {inserted_count} records.")

if __name__ == "__main__":
    run_seed()
