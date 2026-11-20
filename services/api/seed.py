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
from models import SKU, StockEntry, StockExit

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

BRIEFING_SKUS = [
    {
        "name": "Zapatilla blanca clásica - Talla 42",
        "sku": "CLT-SNK-W-42",
        "client_name": "PureStep Footwear",
        "category": "fashion",
        "warehouse": "LA",
        "warehouse_id": "LA",
        "low_stock_threshold": 10,
    },
    {
        "name": "Zapatilla blanca clásica - Talla 42",
        "sku": "CLT-SNK-W-42-Z",
        "client_name": "PureStep Footwear",
        "category": "fashion",
        "warehouse": "ZGZ",
        "warehouse_id": "ZGZ",
        "low_stock_threshold": 10,
    },
    {
        "name": "Auriculares inalámbricos Pro",
        "sku": "TEC-EAR-001",
        "client_name": "SoundWave Electronics",
        "category": "electronics",
        "warehouse": "LA",
        "warehouse_id": "LA",
        "low_stock_threshold": 10,
    },
    {
        "name": "Sérum facial hidratante 30ml",
        "sku": "CSM-SRM-030",
        "client_name": "GlowLab Cosmetics",
        "category": "cosmetics",
        "warehouse": "ZGZ",
        "warehouse_id": "ZGZ",
        "low_stock_threshold": 10,
    },
    {
        "name": "Chino slim fit - marino 32/32",
        "sku": "CLT-CHN-N-32",
        "client_name": "UrbanThread",
        "category": "fashion",
        "warehouse": "LA",
        "warehouse_id": "LA",
        "low_stock_threshold": 10,
    },
    {
        "name": "Cargador rápido USB-C 65W",
        "sku": "TEC-CHG-065",
        "client_name": "SoundWave Electronics",
        "category": "electronics",
        "warehouse": "ZGZ",
        "warehouse_id": "ZGZ",
        "low_stock_threshold": 10,
    },
]

BRIEFING_ENTRIES = [
    {
        "sku": "CLT-SNK-W-42",
        "warehouse": "LA",
        "quantity": 50,
        "reference": "PO-2024-0098",
        "user_uuid": "usr-seed-operator-la",
    },
    {
        "sku": "CLT-SNK-W-42",
        "warehouse": "LA",
        "quantity": 30,
        "reference": "GR-LA-0234",
        "user_uuid": "usr-seed-operator-la",
    },
    {
        "sku": "CLT-SNK-W-42-Z",
        "warehouse": "ZGZ",
        "quantity": 40,
        "reference": "PO-2024-0102",
        "user_uuid": "usr-seed-operator-zgz",
    },
    {
        "sku": "TEC-EAR-001",
        "warehouse": "LA",
        "quantity": 25,
        "reference": "PO-2024-0115",
        "user_uuid": "usr-seed-operator-la",
    },
    {
        "sku": "CSM-SRM-030",
        "warehouse": "ZGZ",
        "quantity": 60,
        "reference": "PO-2024-0120",
        "user_uuid": "usr-seed-operator-zgz",
    },
]

BRIEFING_EXITS = [
    {
        "sku": "CLT-SNK-W-42",
        "warehouse": "LA",
        "quantity": 15,
        "exit_type": "dispatch",
        "tracking_number": "1Z999AA10123456784",
        "user_uuid": "usr-seed-coord-la",
    },
    {
        "sku": "CLT-SNK-W-42",
        "warehouse": "LA",
        "quantity": 2,
        "exit_type": "loss",
        "tracking_number": None,
        "user_uuid": "usr-seed-coord-la",
    },
    {
        "sku": "CLT-SNK-W-42-Z",
        "warehouse": "ZGZ",
        "quantity": 10,
        "exit_type": "dispatch",
        "tracking_number": "1Z888BB20987654321",
        "user_uuid": "usr-seed-coord-zgz",
    },
]

INITIAL_PRODUCTS = [
    {
        "sku": "SKU-LA-1001",
        "name": "Heavy Duty Shipping Pallet",
        "client_name": "PureStep Footwear",
        "category": "fashion",
        "warehouse": "LA",
        "warehouse_id": "wh-la",
        "low_stock_threshold": 15,
        "initial_stock": 100,
    },
    {
        "sku": "SKU-ZGZ-2002",
        "name": "Express Cargo Box",
        "client_name": "PureStep Footwear",
        "category": "fashion",
        "warehouse": "ZGZ",
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

        # 2. Seed SQLModel Inventory Products, StockEntries and StockExits
        inserted_products = 0
        inserted_entries = 0
        inserted_exits = 0
        try:
            init_db(engine)
            with Session(engine) as session:
                # Seed Briefing SKUs
                for p_data in BRIEFING_SKUS:
                    existing_sku = session.exec(select(SKU).where(SKU.sku == p_data["sku"])).first()
                    if not existing_sku:
                        sku_obj = SKU(
                            sku=p_data["sku"],
                            name=p_data["name"],
                            client_name=p_data.get("client_name", "PureStep Footwear"),
                            category=p_data.get("category", "fashion"),
                            warehouse=p_data.get("warehouse", "LA"),
                            warehouse_id=p_data.get("warehouse_id", "LA"),
                            low_stock_threshold=p_data.get("low_stock_threshold", 10),
                        )
                        session.add(sku_obj)
                        session.commit()
                        session.refresh(sku_obj)
                        inserted_products += 1

                # Seed Initial legacy products
                for p_data in INITIAL_PRODUCTS:
                    existing_sku = session.exec(select(SKU).where(SKU.sku == p_data["sku"])).first()
                    if not existing_sku:
                        sku_obj = SKU(
                            sku=p_data["sku"],
                            name=p_data["name"],
                            client_name=p_data.get("client_name", "PureStep Footwear"),
                            category=p_data.get("category", "fashion"),
                            warehouse=p_data.get("warehouse", "LA"),
                            warehouse_id=p_data.get("warehouse_id", "wh-la"),
                            low_stock_threshold=p_data.get("low_stock_threshold", 10),
                        )
                        session.add(sku_obj)
                        session.commit()
                        session.refresh(sku_obj)

                        stock_entry = StockEntry(
                            sku_id=sku_obj.id,
                            warehouse=sku_obj.warehouse,
                            warehouse_id=sku_obj.warehouse_id,
                            quantity=p_data["initial_stock"],
                            reference="INIT-SEED",
                            user_uuid="usr-seed-system",
                        )
                        session.add(stock_entry)
                        session.commit()
                        inserted_products += 1

                # Seed Briefing StockEntries
                for entry_data in BRIEFING_ENTRIES:
                    sku_obj = session.exec(select(SKU).where(SKU.sku == entry_data["sku"])).first()
                    if sku_obj:
                        existing_entry = session.exec(
                            select(StockEntry).where(
                                (StockEntry.sku_id == sku_obj.id)
                                & (StockEntry.reference == entry_data["reference"])
                            )
                        ).first()
                        if not existing_entry:
                            stock_entry = StockEntry(
                                sku_id=sku_obj.id,
                                warehouse=entry_data["warehouse"],
                                warehouse_id=entry_data["warehouse"],
                                quantity=entry_data["quantity"],
                                reference=entry_data["reference"],
                                user_uuid=entry_data["user_uuid"],
                            )
                            session.add(stock_entry)
                            session.commit()
                            inserted_entries += 1

                # Seed Briefing StockExits
                for exit_data in BRIEFING_EXITS:
                    sku_obj = session.exec(select(SKU).where(SKU.sku == exit_data["sku"])).first()
                    if sku_obj:
                        existing_exit = session.exec(
                            select(StockExit).where(
                                (StockExit.sku_id == sku_obj.id)
                                & (StockExit.exit_type == exit_data["exit_type"])
                                & (StockExit.quantity == exit_data["quantity"])
                            )
                        ).first()
                        if not existing_exit:
                            stock_exit = StockExit(
                                sku_id=sku_obj.id,
                                warehouse=exit_data["warehouse"],
                                warehouse_id=exit_data["warehouse"],
                                quantity=exit_data["quantity"],
                                exit_type=exit_data["exit_type"],
                                tracking_number=exit_data["tracking_number"],
                                user_uuid=exit_data["user_uuid"],
                            )
                            session.add(stock_exit)
                            session.commit()
                            inserted_exits += 1

        except Exception as sql_err:
            print(f"[WARN] Relational inventory seeding skipped: {sql_err}")

        print(
            f"Seeder executed successfully. Inserted {inserted_suppliers} suppliers, "
            f"{inserted_products} products, {inserted_entries} entries, and {inserted_exits} exits."
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
