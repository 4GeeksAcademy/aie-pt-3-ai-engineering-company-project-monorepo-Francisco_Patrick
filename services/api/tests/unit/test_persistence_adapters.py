"""Unit tests for driven persistence and infrastructure adapters.

Verifies TinyDB and SQLModel repository adapters and infrastructure notification/security adapters.
"""

from typing import Generator
import pytest
from sqlmodel import Session, SQLModel, create_engine

from domain.auth.models import Profile, User
from domain.incidents.models import Incident
from domain.inventory.models import SKU, StockEntry, StockExit
from domain.suppliers.models import Supplier
from infrastructure.notifications.email_adapter import EmailAdapter, mask_email
from infrastructure.persistence.sqlmodel.inventory_repository import (
    SQLModelInventoryRepository,
)
from infrastructure.persistence.sqlmodel.models import (
    SKU as ORMSKU,
    StockEntry as ORMStockEntry,
    StockExit as ORMStockExit,
)
from infrastructure.persistence.tinydb.audit_log_repository import (
    TinyDBAuditLogRepository,
)
from infrastructure.persistence.tinydb.incident_repository import (
    TinyDBIncidentRepository,
)
from infrastructure.persistence.tinydb.password_reset_repository import (
    TinyDBPasswordResetTokenRepository,
)
from infrastructure.persistence.tinydb.profile_repository import (
    TinyDBProfileRepository,
)
from infrastructure.persistence.tinydb.supplier_repository import (
    TinyDBSupplierRepository,
)
from infrastructure.persistence.tinydb.user_repository import (
    TinyDBUserRepository,
)
from infrastructure.security.jwt_security_adapter import JwtSecurityAdapter
from tinydb import TinyDB
from tinydb.storages import MemoryStorage


# --- Fixtures ---
@pytest.fixture
def memory_tinydb() -> TinyDB:
    """In-memory TinyDB instance isolating repository tests from disk."""
    return TinyDB(storage=MemoryStorage)


@pytest.fixture
def memory_sqlmodel_session() -> Generator[Session, None, None]:
    """In-memory SQLite SQLModel session isolating repository tests."""
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session


# --- Supplier Repository Tests ---
def test_tinydb_supplier_repository_crud(memory_tinydb: TinyDB):
    repo = TinyDBSupplierRepository(db=memory_tinydb)

    # Create
    sup = Supplier(
        name="Mediterranean Shipping",
        country="Greece",
        category="ocean_freight",
        cost_per_kg=3.40,
        status="active",
    )
    created = repo.create(sup)
    assert created.id is not None

    # Get by ID
    found = repo.get_by_id(created.id)
    assert found is not None
    assert found.name == "Mediterranean Shipping"

    # List all
    all_sups = repo.list_all(country="Greece")
    assert len(all_sups) == 1

    # Update rate
    updated_rate = repo.update_rate(created.id, 4.10)
    assert updated_rate is not None
    assert updated_rate.cost_per_kg == 4.10

    # Update status
    updated_status = repo.update_status(created.id, "suspended")
    assert updated_status is not None
    assert updated_status.status == "suspended"

    # Delete
    deleted = repo.delete(created.id)
    assert deleted is True
    assert repo.get_by_id(created.id) is None


# --- User & Profile Repository Tests ---
def test_tinydb_user_and_profile_repository(memory_tinydb: TinyDB):
    user_repo = TinyDBUserRepository(db=memory_tinydb)
    profile_repo = TinyDBProfileRepository(db=memory_tinydb)

    user = User(
        id="usr_test_100",
        email="test100@trackflow.com",
        hashed_password="bcrypt_hash",
        role="user",
        is_active=True,
        created_at="2026-10-13T10:00:00Z",
    )
    saved_user = user_repo.save(user)
    assert saved_user.id == "usr_test_100"

    found_by_email = user_repo.get_by_email("test100@trackflow.com")
    assert found_by_email is not None
    assert found_by_email.id == "usr_test_100"

    profile = Profile(
        user_id="usr_test_100",
        name="Arthur Dent",
        phone="+4412345678",
    )
    saved_profile = profile_repo.save(profile)
    assert saved_profile.user_id == "usr_test_100"

    found_profile = profile_repo.get_by_user_id("usr_test_100")
    assert found_profile is not None
    assert found_profile.name == "Arthur Dent"

    # Clean up
    assert user_repo.delete("usr_test_100") is True
    assert profile_repo.delete_by_user_id("usr_test_100") is True


# --- Incident Repository Tests ---
def test_tinydb_incident_repository(memory_tinydb: TinyDB):
    repo = TinyDBIncidentRepository(db=memory_tinydb)

    inc = Incident(
        title="Conveyor belt jam",
        description="Line 2 stopped",
        category="warehouse",
        branch="north",
        legacy_id="CSV_99",
    )
    repo.save(inc)

    found = repo.find_by_id(inc.id)
    assert found is not None
    assert found.title == "Conveyor belt jam"

    found_legacy = repo.find_by_legacy_id("CSV_99")
    assert found_legacy is not None
    assert found_legacy.id == inc.id

    summary = repo.count_summary()
    assert summary["total_incidents"] == 1
    assert summary["by_status"]["open"] == 1
    assert summary["by_category"]["warehouse"] == 1


# --- Password Reset & Audit Log Repository Tests ---
def test_tinydb_password_reset_and_audit_log(memory_tinydb: TinyDB):
    token_repo = TinyDBPasswordResetTokenRepository(db=memory_tinydb)
    audit_repo = TinyDBAuditLogRepository(db=memory_tinydb)

    token_doc = token_repo.create_token(
        user_id="usr_test_200", raw_token="secret_reset_token", expires_in_minutes=15
    )
    assert token_doc["user_id"] == "usr_test_200"

    valid_token = token_repo.get_valid_token("secret_reset_token")
    assert valid_token is not None

    assert token_repo.mark_used(token_doc["id"]) is True
    assert token_repo.get_valid_token("secret_reset_token") is None

    audit_entry = audit_repo.log_event(
        "test_event", "usr_test_200", "127.0.0.1", "details test"
    )
    assert audit_entry["event_type"] == "test_event"


# --- SQLModel Inventory Repository Tests ---
def test_sqlmodel_inventory_repository(memory_sqlmodel_session: Session):
    repo = SQLModelInventoryRepository(session=memory_sqlmodel_session)

    # Create SKU
    sku = SKU(
        sku="SKU-SQL-01",
        name="Industrial Valve",
        warehouse_id="wh-central",
        low_stock_threshold=5,
    )
    created_sku = repo.create_sku(sku)
    assert created_sku.id is not None

    # Calculate initial stock
    assert repo.calculate_stock(created_sku.id, "wh-central") == 0

    # Inbound entry
    repo.add_inbound_entry(
        StockEntry(
            sku_id=created_sku.id,
            warehouse_id="wh-central",
            quantity=50,
            user_uuid="usr_op",
        )
    )
    assert repo.calculate_stock(created_sku.id, "wh-central") == 50

    # Outbound exit
    repo.add_outbound_exit(
        StockExit(
            sku_id=created_sku.id,
            warehouse_id="wh-central",
            quantity=15,
            user_uuid="usr_op",
        )
    )
    assert repo.calculate_stock(created_sku.id, "wh-central") == 35

    # List products
    products = repo.list_all_products()
    assert len(products) == 1
    assert products[0].current_stock == 35
    assert products[0].is_low_stock is False

    # List orders
    orders = repo.list_orders()
    assert len(orders) == 2


# --- Email & Security Adapters ---
def test_email_adapter_mock_mode():
    adapter = EmailAdapter(api_key=None)
    assert adapter.send_password_reset("user@example.com", "http://reset.link") is True
    assert mask_email("user@example.com") == "u***r@example.com"


def test_jwt_security_adapter():
    adapter = JwtSecurityAdapter()
    hashed = adapter.hash_password("SuperSecret123")
    assert adapter.verify_password("SuperSecret123", hashed) is True
    assert adapter.verify_password("WrongSecret", hashed) is False

    token = adapter.create_access_token(subject="usr_test_jwt")
    subject = adapter.decode_access_token(token)
    assert subject == "usr_test_jwt"
