"""Database seeder script for TrackFlow Supplier Directory and initial data.

Loads the canonical supplier network from trackflow-BRIEFING.md into TinyDB.
Ensures idempotency (no duplicates on repeated execution) and reports inserted counts.
"""

import copy
import os
import sys
from datetime import datetime, timezone
from tinydb import Query, TinyDB

# Ensure services/api is in Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from infrastructure.database import get_tinydb, engine, init_db
from sqlmodel import Session, select
from models import SKU, StockEntry

# Exact supplier dataset from trackflow-BRIEFING.es.md (Carlos & Ana combined directory)
SUPPLIERS_SEED = [
    {
        "name": "UPS Ground",
        "country": "USA",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 7.45,
        "currency": "USD",
        "status": "active",
        "service_zone": "West Coast",
        "contact_email": "business@ups.com",
        "notes": "Carrier principal para entregas locales en Los Ángeles y alrededores.",
    },
    {
        "name": "FedEx Ground",
        "country": "USA",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 7.90,
        "currency": "USD",
        "status": "active",
        "service_zone": "Continental USA",
        "contact_email": "business.solutions@fedex.com",
    },
    {
        "name": "DHL Express USA",
        "country": "USA",
        "categories": ["carrier_last_mile", "carrier_international"],
        "rate_per_shipment": 14.20,
        "currency": "USD",
        "status": "active",
        "service_zone": "Continental USA + International",
        "contact_email": "business.us@dhl.com",
        "notes": "Usado para envíos urgentes y exportaciones a Europa.",
    },
    {
        "name": "OnTrac",
        "country": "USA",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 6.10,
        "currency": "USD",
        "status": "active",
        "service_zone": "West Coast",
        "contact_email": "solutions@ontrac.com",
        "notes": "Carrier regional. Mejor tarifa en la zona de Los Ángeles.",
    },
    {
        "name": "Laser Ship",
        "country": "USA",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 5.80,
        "currency": "USD",
        "status": "suspended",
        "service_zone": "East Coast",
        "contact_email": "business@lasership.com",
        "notes": "Suspendido. Tasa de incidencias superior al 8% en Q3.",
    },
    {
        "name": "PackSource LA",
        "country": "USA",
        "categories": ["packaging_materials"],
        "rate_per_shipment": 0.42,
        "currency": "USD",
        "status": "active",
        "contact_email": "orders@packsource.com",
        "notes": "Cajas, relleno y precinto para el almacén de Los Ángeles.",
    },
    {
        "name": "CleanTeam West",
        "country": "USA",
        "categories": ["cleaning_and_facilities"],
        "rate_per_shipment": 1800.0,
        "currency": "USD",
        "status": "active",
        "contact_email": "accounts@cleanteamwest.com",
        "notes": "Tarifa mensual por servicio de limpieza del almacén de LA.",
    },
    {
        "name": "MRW España",
        "country": "Spain",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 4.90,
        "currency": "EUR",
        "status": "active",
        "service_zone": "Península Ibérica",
        "contact_email": "clientes.empresa@mrw.es",
        "notes": "Carrier principal para entregas en España. Contrato negociado por volumen.",
    },
    {
        "name": "SEUR",
        "country": "Spain",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 5.20,
        "currency": "EUR",
        "status": "active",
        "service_zone": "Península Ibérica + Baleares",
        "contact_email": "grandes.cuentas@seur.com",
    },
    {
        "name": "DHL Express España",
        "country": "Spain",
        "categories": ["carrier_last_mile", "carrier_international"],
        "rate_per_shipment": 12.80,
        "currency": "EUR",
        "status": "active",
        "service_zone": "España + Internacional",
        "contact_email": "business.es@dhl.com",
        "notes": "Envíos urgentes y exportaciones desde Zaragoza.",
    },
    {
        "name": "Nacex",
        "country": "Spain",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 4.60,
        "currency": "EUR",
        "status": "active",
        "service_zone": "Aragón y zona norte",
        "contact_email": "empresas@nacex.es",
        "notes": "Carrier regional con buena cobertura en Aragón.",
    },
    {
        "name": "Logística Inversa Iberia",
        "country": "Spain",
        "categories": ["reverse_logistics"],
        "rate_per_shipment": 6.30,
        "currency": "EUR",
        "status": "active",
        "contact_email": "operaciones@liiberia.es",
        "notes": "Gestión de devoluciones para el almacén de Zaragoza.",
    },
    {
        "name": "Embalajes Zaragoza S.L.",
        "country": "Spain",
        "categories": ["packaging_materials"],
        "rate_per_shipment": 0.28,
        "currency": "EUR",
        "status": "active",
        "contact_email": "pedidos@embalajeszgz.es",
    },
    {
        "name": "SAP WM Cloud",
        "country": "USA",
        "categories": ["it_and_wms_software"],
        "rate_per_shipment": 2200.0,
        "currency": "USD",
        "status": "suspended",
        "contact_email": "enterprise@sap.com",
        "notes": "Suspendido. Andrés está evaluando alternativas más ligeras para el almacén de LA.",
    },
    {
        "name": "ReturnBear",
        "country": "USA",
        "categories": ["reverse_logistics"],
        "rate_per_shipment": 4.15,
        "currency": "USD",
        "status": "active",
        "service_zone": "West Coast",
        "contact_email": "partnerships@returnbear.com",
        "notes": "Gestión de devoluciones para clientes de Los Ángeles.",
    },
]

INITIAL_PRODUCTS = [
    {
        "sku": "SKU-LA-1001",
        "name": "Heavy Duty Shipping Pallet",
        "warehouse_id": "wh-la",
        "low_stock_threshold": 15,
        "initial_stock": 100,
    },
    {
        "sku": "SKU-ZGZ-2002",
        "name": "Express Cargo Box",
        "warehouse_id": "wh-zgz",
        "low_stock_threshold": 10,
        "initial_stock": 50,
    },
]


def get_current_time_str() -> str:
    """Return ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def run_seed() -> int:
    """Execute seeding for suppliers in TinyDB and inventory products in SQLModel."""
    try:
        # 1. Seed TinyDB Suppliers
        db = get_tinydb()
        table = db.table("suppliers")
        SupplierQuery = Query()

        inserted_suppliers = 0
        for s in SUPPLIERS_SEED:
            exists = table.search(
                (SupplierQuery.name == s["name"]) & (SupplierQuery.country == s["country"])
            )
            if not exists:
                doc = copy.deepcopy(s)
                now_ts = get_current_time_str()
                doc["created_at"] = now_ts
                doc["updated_at"] = now_ts
                # Synchronize legacy aliases
                doc["cost_per_kg"] = s["rate_per_shipment"]
                if "categories" in s and s["categories"]:
                    doc["category"] = s["categories"][0]
                table.insert(doc)
                inserted_suppliers += 1

        # 2. Seed SQLModel Inventory Products & Initial Stock Entries (if available)
        inserted_products = 0
        try:
            init_db(engine)
            with Session(engine) as session:
                for p_data in INITIAL_PRODUCTS:
                    existing_sku = session.exec(select(SKU).where(SKU.sku == p_data["sku"])).first()
                    if not existing_sku:
                        sku_obj = SKU(
                            sku=p_data["sku"],
                            name=p_data["name"],
                            warehouse_id=p_data["warehouse_id"],
                            low_stock_threshold=p_data["low_stock_threshold"],
                        )
                        session.add(sku_obj)
                        session.commit()
                        session.refresh(sku_obj)

                        stock_entry = StockEntry(
                            sku_id=sku_obj.id,
                            warehouse_id=sku_obj.warehouse_id,
                            quantity=p_data["initial_stock"],
                            user_uuid="usr-seed-system",
                        )
                        session.add(stock_entry)
                        session.commit()
                        inserted_products += 1
        except Exception as sql_err:
            print(f"[WARN] Relational inventory seeding skipped: {sql_err}")

        print(
            f"Seeder executed successfully. Inserted {inserted_suppliers} suppliers and {inserted_products} inventory products."
        )
        return inserted_suppliers
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Seeding interrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] Database seeding failed: {e}", file=sys.stderr)
        sys.exit(1)


# Alias seed for backwards compatibility
seed = run_seed

if __name__ == "__main__":
    run_seed()
