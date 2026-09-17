import sys
import os
from tinydb import TinyDB, Query
from datetime import datetime

# Import database module assuming we run this from services/api
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from infrastructure.database import get_tinydb, engine, init_db
from sqlmodel import Session, select
from models import SKU, StockEntry

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

INITIAL_PRODUCTS = [
    {
        "sku": "SKU-LA-1001",
        "name": "Heavy Duty Shipping Pallet",
        "warehouse_id": "wh-la",
        "low_stock_threshold": 15,
        "initial_stock": 100
    },
    {
        "sku": "SKU-ZGZ-2002",
        "name": "Express Cargo Box",
        "warehouse_id": "wh-zgz",
        "low_stock_threshold": 10,
        "initial_stock": 50
    }
]

def get_current_time_str() -> str:
    return datetime.utcnow().isoformat()

def run_seed():
    try:
        # 1. Seed TinyDB Suppliers
        db = get_tinydb()
        table = db.table('suppliers')
        SupplierQuery = Query()
        
        inserted_suppliers = 0
        for s in INITIAL_SUPPLIERS:
            exists = table.search((SupplierQuery.name == s["name"]) & (SupplierQuery.country == s["country"]))
            if not exists:
                s["updated_at"] = get_current_time_str()
                table.insert(s)
                inserted_suppliers += 1

        # 2. Seed SQLModel Inventory Products & Initial Stock Entries
        init_db(engine)
        inserted_products = 0
        with Session(engine) as session:
            for p_data in INITIAL_PRODUCTS:
                existing_sku = session.exec(select(SKU).where(SKU.sku == p_data["sku"])).first()
                if not existing_sku:
                    sku_obj = SKU(
                        sku=p_data["sku"],
                        name=p_data["name"],
                        warehouse_id=p_data["warehouse_id"],
                        low_stock_threshold=p_data["low_stock_threshold"]
                    )
                    session.add(sku_obj)
                    session.commit()
                    session.refresh(sku_obj)

                    stock_entry = StockEntry(
                        sku_id=sku_obj.id,
                        warehouse_id=sku_obj.warehouse_id,
                        quantity=p_data["initial_stock"],
                        user_uuid="usr-seed-system"
                    )
                    session.add(stock_entry)
                    session.commit()
                    inserted_products += 1

        print(f"Seeder executed successfully. Inserted {inserted_suppliers} suppliers and {inserted_products} inventory products.")
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Seeding interrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] Database seeding failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_seed()

