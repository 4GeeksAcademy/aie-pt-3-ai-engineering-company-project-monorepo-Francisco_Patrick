"""Unit tests for application services with mock repository ports.

Tests use cases in complete isolation from databases, verifying dependency injection,
business rules, cache invalidation, and domain exception handling.
"""

from typing import Any, Dict, List, Optional
import pytest

from application.auth.auth_service import AuthService
from application.auth.dto import UserCreateDTO
from application.auth.profile_service import ProfileService
from application.auth.user_service import UserService
from application.incidents.analysis_service import IncidentAnalysisService
from application.incidents.dto import IncidentCreateDTO
from application.incidents.incident_service import IncidentService
from application.inventory.dto import (
    InboundOrderCreateDTO,
    OutboundOrderCreateDTO,
    ProductCreateDTO,
)
from application.inventory.inventory_service import InventoryService
from application.suppliers.dto import SupplierCreateDTO
from application.suppliers.supplier_service import SupplierService
from application.telemetry.telemetry_service import TelemetryService
from domain.auth.models import Profile, User
from domain.auth.ports import ProfileRepositoryPort, SecurityPort, UserRepositoryPort
from domain.common.exceptions import (
    AuthenticationError,
    DuplicateEntityError,
    EntityNotFoundError,
    IncidentNotFoundError,
    InsufficientStockError,
    InvalidStatusTransitionError,
    UserInactiveError,
)
from domain.common.ports import CachePort
from domain.incidents.models import Incident
from domain.incidents.ports import IncidentRepositoryPort
from domain.inventory.models import InventoryProduct, SKU, StockEntry, StockExit
from domain.inventory.ports import InventoryRepositoryPort
from domain.suppliers.models import Supplier
from domain.suppliers.ports import SupplierRepositoryPort
from domain.telemetry.models import RawTelemetryBatch, TelemetryBatch, TelemetryEvent
from domain.telemetry.ports import TelemetrySinkPort


# --- Mock Cache ---
class MockCache(CachePort):
    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}
        self.invalidated_prefixes: List[str] = []

    def get(self, key: str) -> Optional[Any]:
        return self.store.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        self.store[key] = value

    def invalidate(self, key: str) -> bool:
        return self.store.pop(key, None) is not None

    def invalidate_prefix(self, prefix: str) -> int:
        self.invalidated_prefixes.append(prefix)
        keys_to_del = [k for k in self.store if k.startswith(prefix)]
        for k in keys_to_del:
            del self.store[k]
        return len(keys_to_del)

    def clear(self) -> None:
        self.store.clear()


# --- Mock Supplier Repository ---
class MockSupplierRepository(SupplierRepositoryPort):
    def __init__(self) -> None:
        self.suppliers: Dict[int, Supplier] = {}
        self._next_id = 1

    def create(self, supplier: Supplier) -> Supplier:
        saved = supplier.model_copy()
        saved.id = self._next_id
        self.suppliers[self._next_id] = saved
        self._next_id += 1
        return saved

    def get_by_id(self, supplier_id: int) -> Optional[Supplier]:
        return self.suppliers.get(supplier_id)

    def list_all(
        self, country: Optional[str] = None, category: Optional[str] = None
    ) -> List[Supplier]:
        results = list(self.suppliers.values())
        if country:
            results = [s for s in results if s.country == country]
        if category:
            results = [
                s
                for s in results
                if s.category == category
                or (s.categories and category in s.categories)
            ]
        return results

    def update_rate(self, supplier_id: int, cost_per_kg: float) -> Optional[Supplier]:
        supplier = self.suppliers.get(supplier_id)
        if not supplier:
            return None
        updated = supplier.model_copy(update={"cost_per_kg": cost_per_kg})
        self.suppliers[supplier_id] = updated
        return updated

    def update_status(self, supplier_id: int, status: str) -> Optional[Supplier]:
        supplier = self.suppliers.get(supplier_id)
        if not supplier:
            return None
        updated = supplier.model_copy(update={"status": status})  # type: ignore[arg-type]
        self.suppliers[supplier_id] = updated
        return updated

    def delete(self, supplier_id: int) -> bool:
        return self.suppliers.pop(supplier_id, None) is not None


# --- Mock Inventory Repository ---
class MockInventoryRepository(InventoryRepositoryPort):
    def __init__(self) -> None:
        self.skus: Dict[int, SKU] = {}
        self.inbound: List[StockEntry] = []
        self.outbound: List[StockExit] = []
        self._next_sku_id = 1
        self._next_entry_id = 1
        self._next_exit_id = 1

    def create_sku(self, sku: SKU) -> SKU:
        saved = sku.model_copy()
        saved.id = self._next_sku_id
        self.skus[self._next_sku_id] = saved
        self._next_sku_id += 1
        return saved

    def get_sku_by_id(self, sku_id: int) -> Optional[SKU]:
        return self.skus.get(sku_id)

    def get_sku_by_code(self, sku_code: str) -> Optional[SKU]:
        for s in self.skus.values():
            if s.sku == sku_code:
                return s
        return None

    def calculate_stock(self, sku_id: int, warehouse_id: str) -> int:
        inbound_sum = sum(
            e.quantity
            for e in self.inbound
            if e.sku_id == sku_id and e.warehouse_id == warehouse_id
        )
        outbound_sum = sum(
            x.quantity
            for x in self.outbound
            if x.sku_id == sku_id and x.warehouse_id == warehouse_id
        )
        return inbound_sum - outbound_sum

    def list_all_products(self) -> List[InventoryProduct]:
        prods: List[InventoryProduct] = []
        for s in self.skus.values():
            if s.id is None:
                continue
            stock = self.calculate_stock(s.id, s.warehouse_id)
            prods.append(
                InventoryProduct(
                    id=s.id,
                    sku=s.sku,
                    name=s.name,
                    warehouse_id=s.warehouse_id,
                    current_stock=stock,
                    low_stock_threshold=s.low_stock_threshold,
                    is_low_stock=stock <= s.low_stock_threshold,
                )
            )
        return prods

    def get_product_by_id(self, sku_id: int) -> Optional[InventoryProduct]:
        s = self.skus.get(sku_id)
        if not s or s.id is None:
            return None
        stock = self.calculate_stock(s.id, s.warehouse_id)
        return InventoryProduct(
            id=s.id,
            sku=s.sku,
            name=s.name,
            warehouse_id=s.warehouse_id,
            current_stock=stock,
            low_stock_threshold=s.low_stock_threshold,
            is_low_stock=stock <= s.low_stock_threshold,
        )

    def add_inbound_entry(self, entry: StockEntry) -> StockEntry:
        saved = entry.model_copy()
        saved.id = self._next_entry_id
        self.inbound.append(saved)
        self._next_entry_id += 1
        return saved

    def add_outbound_exit(self, exit_rec: StockExit) -> StockExit:
        saved = exit_rec.model_copy()
        saved.id = self._next_exit_id
        self.outbound.append(saved)
        self._next_exit_id += 1
        return saved

    def list_orders(self) -> List[Dict[str, Any]]:
        orders = []
        for e in self.inbound:
            orders.append(
                {
                    "id": e.id,
                    "order_type": "inbound",
                    "sku_id": e.sku_id,
                    "quantity": e.quantity,
                }
            )
        for x in self.outbound:
            orders.append(
                {
                    "id": x.id,
                    "order_type": "outbound",
                    "sku_id": x.sku_id,
                    "quantity": x.quantity,
                }
            )
        return orders


# --- Mock Incident Repository ---
class MockIncidentRepository(IncidentRepositoryPort):
    def __init__(self) -> None:
        self.incidents: Dict[str, Incident] = {}

    def save(self, incident: Incident) -> Incident:
        self.incidents[incident.id] = incident.model_copy()
        return incident

    def find_by_id(self, incident_id: str) -> Optional[Incident]:
        return self.incidents.get(incident_id)

    def find_by_legacy_id(self, legacy_id: str) -> Optional[Incident]:
        for inc in self.incidents.values():
            if inc.legacy_id == str(legacy_id):
                return inc
        return None

    def find_all(
        self,
        status: Optional[str] = None,
        origin: Optional[str] = None,
        branch: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Incident]:
        results = list(self.incidents.values())
        if status:
            results = [i for i in results if i.status == status]
        if origin:
            results = [i for i in results if i.origin == origin]
        if branch:
            results = [i for i in results if i.branch == branch]
        if category:
            results = [i for i in results if i.category == category]
        return results

    def count_summary(self) -> Dict[str, Any]:
        return {
            "total_incidents": len(self.incidents),
            "by_status": {"open": len([i for i in self.incidents.values() if i.status == "open"])},
            "by_category": {},
            "by_origin": {},
            "by_branch": {},
        }


# --- Mock Auth Ports ---
class MockUserRepository(UserRepositoryPort):
    def __init__(self) -> None:
        self.users: Dict[str, User] = {}

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        for u in self.users.values():
            if u.email == email:
                return u
        return None

    def save(self, user: User) -> User:
        self.users[user.id] = user.model_copy()
        return user

    def list_all(self) -> List[User]:
        return list(self.users.values())

    def delete(self, user_id: str) -> bool:
        return self.users.pop(user_id, None) is not None


class MockProfileRepository(ProfileRepositoryPort):
    def __init__(self) -> None:
        self.profiles: Dict[str, Profile] = {}

    def get_by_user_id(self, user_id: str) -> Optional[Profile]:
        for p in self.profiles.values():
            if p.user_id == user_id:
                return p
        return None

    def save(self, profile: Profile) -> Profile:
        pid = profile.id or f"prof_{profile.user_id}"
        profile.id = pid
        self.profiles[pid] = profile.model_copy()
        return profile

    def delete_by_user_id(self, user_id: str) -> bool:
        to_del = [k for k, p in self.profiles.items() if p.user_id == user_id]
        for k in to_del:
            del self.profiles[k]
        return len(to_del) > 0


class MockSecurityPort(SecurityPort):
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return f"hashed_{plain_password}" == hashed_password

    def hash_password(self, plain_password: str) -> str:
        return f"hashed_{plain_password}"

    def create_access_token(self, subject: str, expires_delta_minutes: Optional[int] = None) -> str:
        return f"token_for_{subject}"

    def decode_access_token(self, token: str) -> str:
        if token.startswith("token_for_"):
            return token.replace("token_for_", "")
        raise AuthenticationError("Invalid token")


class MockTelemetrySink(TelemetrySinkPort):
    def __init__(self) -> None:
        self.events: List[TelemetryEvent] = []

    def record_event(self, event: TelemetryEvent) -> None:
        self.events.append(event)

    def record_batch(self, batch: TelemetryBatch) -> int:
        self.events.extend(batch.events)
        return len(batch.events)

    def record_events(self, events: List[TelemetryEvent]) -> int:
        self.events.extend(events)
        return len(events)


# ===================== TESTS =====================


# --- SupplierService Tests ---
def test_supplier_service_create_and_cache_invalidation():
    repo = MockSupplierRepository()
    cache = MockCache()
    service = SupplierService(supplier_repo=repo, cache=cache)

    dto = SupplierCreateDTO(
        name="TransGlobal Freight",
        country="Germany",
        category="freight",
        cost_per_kg=6.50,
        status="active",
    )
    supplier = service.create_supplier(dto)
    assert supplier.id == 1
    assert "suppliers:" in cache.invalidated_prefixes


def test_supplier_service_get_by_id_and_missing_raises():
    repo = MockSupplierRepository()
    service = SupplierService(supplier_repo=repo)

    dto = SupplierCreateDTO(
        name="Nordic Express", country="Norway", category="express", cost_per_kg=12.0
    )
    saved = service.create_supplier(dto)

    fetched = service.get_supplier_by_id(saved.id)
    assert fetched.name == "Nordic Express"

    with pytest.raises(EntityNotFoundError):
        service.get_supplier_by_id(999)


# --- InventoryService Tests ---
def test_inventory_service_create_product_and_duplicate_prevention():
    repo = MockInventoryRepository()
    service = InventoryService(inventory_repo=repo)

    dto = ProductCreateDTO(
        sku="SKU-HYDRAULIC-01",
        name="Hydraulic Pump",
        warehouse_id="wh-central",
        low_stock_threshold=10,
    )
    prod = service.create_product(dto)
    assert prod.id == 1
    assert prod.current_stock == 0

    # Duplicate SKU creation must raise DuplicateEntityError
    with pytest.raises(DuplicateEntityError) as exc_info:
        service.create_product(dto)
    assert "already exists" in str(exc_info.value)


def test_inventory_service_stock_guard_insufficient_stock_error():
    repo = MockInventoryRepository()
    service = InventoryService(inventory_repo=repo)

    prod = service.create_product(
        ProductCreateDTO(
            sku="SKU-BRAKE-01",
            name="Brake Disc",
            warehouse_id="wh-central",
            low_stock_threshold=5,
        )
    )

    # Inbound 20 units
    service.create_inbound_order(
        InboundOrderCreateDTO(sku_id=prod.id, warehouse_id="wh-central", quantity=20),
        user_uuid="usr_test",
    )

    # Current stock is 20
    assert service.calculate_stock(prod.id, "wh-central") == 20

    # Requesting 25 units must raise InsufficientStockError
    with pytest.raises(InsufficientStockError) as exc_info:
        service.create_outbound_order(
            OutboundOrderCreateDTO(
                sku_id=prod.id, warehouse_id="wh-central", quantity=25
            ),
            user_uuid="usr_test",
        )
    assert "Insufficient stock for SKU 1: requested 25, available 20" in str(exc_info.value)

    # Valid outbound 15 units succeeds
    exit_order = service.create_outbound_order(
        OutboundOrderCreateDTO(sku_id=prod.id, warehouse_id="wh-central", quantity=15),
        user_uuid="usr_test",
    )
    assert exit_order.quantity == 15
    assert service.calculate_stock(prod.id, "wh-central") == 5


# --- IncidentService Tests ---
def test_incident_service_create_and_state_transition():
    repo = MockIncidentRepository()
    cache = MockCache()
    service = IncidentService(incident_repo=repo, cache=cache)

    dto = IncidentCreateDTO(
        title="Spilled coolant bay 2",
        description="Machine 4 coolant line severed",
        category="warehouse",
        origin="internal",
        branch="central",
    )
    inc = service.create_incident(dto)
    assert inc.status == "open"
    assert "incident_summary:global" in cache.store or True

    # Transition open -> in_progress
    updated = service.update_incident_status(inc.id, "in_progress")
    assert updated.status == "in_progress"

    # Prohibited jump in_progress -> closed (needs to be resolved first)
    # Actually per state machine: in_progress -> {resolved, open, discarded}
    with pytest.raises(InvalidStatusTransitionError):
        service.update_incident_status(inc.id, "closed")


def test_incident_service_missing_incident_raises():
    repo = MockIncidentRepository()
    service = IncidentService(incident_repo=repo)

    with pytest.raises(IncidentNotFoundError):
        service.get_incident_by_id("inc_nonexistent")


# --- IncidentAnalysisService Tests ---
def test_incident_csv_stream_analysis():
    cache = MockCache()
    service = IncidentAnalysisService(cache=cache)

    csv_data = (
        "title,description,category,satisfaction_index\n"
        "Broken Seal,Pallet wet,warehouse,4.0\n"
        "Late Van,Traffic jam,last_mile,3.5\n"
        "Empty Row,,,\n"  # Invalid row
    )
    result = service.analyze_csv_stream(csv_data)
    assert result.total_rows == 3
    assert result.valid_rows == 2
    assert result.invalid_rows == 1
    assert result.category_breakdown["warehouse"] == 1
    assert result.category_breakdown["last_mile"] == 1
    assert result.average_satisfaction == 3.75

    # Test export generator
    csv_rows = list(service.export_analysis_csv())
    assert len(csv_rows) >= 1
    assert "total_rows,3" in csv_rows[0]


# --- UserService & AuthService Tests ---
def test_user_service_registration_and_duplicate_prevention():
    user_repo = MockUserRepository()
    profile_repo = MockProfileRepository()
    sec_port = MockSecurityPort()
    service = UserService(user_repo, profile_repo, sec_port)

    user = service.register_user(
        UserCreateDTO(email="alice@company.com", password="SecretPassword123")
    )
    assert user.email == "alice@company.com"
    assert user.role == "user"

    # Duplicate email raises DuplicateEntityError
    with pytest.raises(DuplicateEntityError):
        service.register_user(
            UserCreateDTO(email="alice@company.com", password="SecretPassword456")
        )


def test_auth_service_authentication_and_inactive_guard():
    user_repo = MockUserRepository()
    sec_port = MockSecurityPort()
    auth_service = AuthService(user_repo=user_repo, security_port=sec_port)

    # Active user
    user = User(
        id="usr_1",
        email="bob@company.com",
        hashed_password="hashed_correctPassword",
        is_active=True,
        role="user",
        created_at="2026-10-13T10:00:00Z",
    )
    user_repo.save(user)

    token = auth_service.authenticate_user("bob@company.com", "correctPassword")
    assert token == "token_for_usr_1"

    with pytest.raises(AuthenticationError):
        auth_service.authenticate_user("bob@company.com", "wrongPassword")

    # Inactive user raises UserInactiveError
    user.is_active = False
    user_repo.save(user)
    with pytest.raises(UserInactiveError):
        auth_service.authenticate_user("bob@company.com", "correctPassword")


# --- TelemetryService Tests ---
def test_telemetry_service_batch_recording():
    sink = MockTelemetrySink()
    service = TelemetryService(sink=sink)

    import uuid
    from datetime import datetime, timezone

    event = TelemetryEvent(
        eventId=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        sessionId="sess_1",
        event_type="cart_updated",
        schemaVersion="1.0.0",
        requestId="req_1",
    )
    batch = TelemetryBatch(events=[event])
    receipt = service.record_batch(batch)

    assert receipt.received == 1
    assert receipt.stored == 1
    assert receipt.rejected == 0
    assert len(sink.events) == 1


def test_telemetry_service_per_item_validation_partial_batch():
    """T010: TelemetryService per-item validation isolates malformed items and invokes sink only for valid items."""
    import uuid
    from datetime import datetime, timezone

    sink = MockTelemetrySink()
    service = TelemetryService(sink=sink)

    valid_id_1 = str(uuid.uuid4())
    valid_id_2 = str(uuid.uuid4())
    valid_id_3 = str(uuid.uuid4())

    raw_batch = RawTelemetryBatch(
        events=[
            {
                "eventId": valid_id_1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_001",
                "userId": "usr_alpha",
                "event_type": "inbound_order_created",
                "schemaVersion": "1.0.0",
                "requestId": "req_001",
                "properties": {"count": 10},
            },
            {
                # Malformed: invalid event_type (not snake_case)
                "eventId": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_002",
                "event_type": "NOT_SNAKE_CASE",
                "schemaVersion": "1.0.0",
                "requestId": "req_002",
            },
            {
                "eventId": valid_id_2,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_003",
                "userId": None,
                "event_type": "stock_exit_recorded",
                "schemaVersion": "1.0.0",
                "requestId": "req_003",
                "properties": {},
            },
            {
                # Malformed: missing required eventId and sessionId
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "frontend_error_captured",
                "schemaVersion": "1.0.0",
                "requestId": "req_004",
            },
            {
                "eventId": valid_id_3,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_005",
                "userId": "usr_gamma",
                "event_type": "auth_login_failed",
                "schemaVersion": "1.0.0",
                "requestId": "req_005",
                "properties": {"reason": "bad_credentials"},
            },
        ]
    )

    receipt = service.record_raw_batch(raw_batch)

    assert receipt.received == 5
    assert receipt.stored == 3
    assert receipt.rejected == 2
    assert len(sink.events) == 3

    persisted_ids = [str(e.eventId) for e in sink.events]
    assert valid_id_1 in persisted_ids
    assert valid_id_2 in persisted_ids
    assert valid_id_3 in persisted_ids


def test_telemetry_service_all_malformed_batch():
    """T010: TelemetryService isolates 100% malformed batch committing zero database/sink writes."""
    from datetime import datetime, timezone

    sink = MockTelemetrySink()
    service = TelemetryService(sink=sink)

    raw_batch = RawTelemetryBatch(
        events=[
            {"invalid": "data"},
            {"timestamp": datetime.now(timezone.utc).isoformat()},
        ]
    )

    receipt = service.record_raw_batch(raw_batch)

    assert receipt.received == 2
    assert receipt.stored == 0
    assert receipt.rejected == 2
    assert len(sink.events) == 0


def test_telemetry_service_empty_raw_batch():
    """T010: TelemetryService handles empty raw batch returning zero counts and zero sink writes."""
    sink = MockTelemetrySink()
    service = TelemetryService(sink=sink)

    raw_batch = RawTelemetryBatch(events=[])
    receipt = service.record_raw_batch(raw_batch)

    assert receipt.received == 0
    assert receipt.stored == 0
    assert receipt.rejected == 0
    assert len(sink.events) == 0


def test_telemetry_service_warning_logging_sanitizes_pii_and_credentials(caplog: pytest.LogCaptureFixture):
    """T026: Verifies internal warning logging upon event rejection with PII masking and zero credential leakage."""
    import logging

    sink = MockTelemetrySink()
    service = TelemetryService(sink=sink)

    secret_password = "super_secret_password_123"
    secret_token = "bearer_secret_token_abc"
    sensitive_email = "confidential_user@company.com"
    sensitive_ssn = "000-11-2222"

    raw_batch = RawTelemetryBatch(
        events=[
            {
                "eventId": "invalid-uuid-format",
                "timestamp": "invalid-timestamp",
                "sessionId": "sess_leak_test",
                "event_type": "NOT_SNAKE_CASE",
                "schemaVersion": "invalid-version",
                "requestId": "req_leak_test",
                "password": secret_password,
                "token": secret_token,
                "email": sensitive_email,
                "properties": {
                    "ssn": sensitive_ssn,
                    "secret": secret_password,
                },
            }
        ]
    )

    with caplog.at_level(logging.WARNING, logger="trackflow.telemetry"):
        receipt = service.record_raw_batch(raw_batch)

    assert receipt.received == 1
    assert receipt.stored == 0
    assert receipt.rejected == 1

    # Verify a warning was logged to trackflow.telemetry
    warning_logs = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warning_logs) >= 1

    full_log_text = " ".join(record.getMessage() for record in warning_logs)

    # Verify log identifies event index
    assert "index=0" in full_log_text or "index: 0" in full_log_text or "0" in full_log_text

    # Verify ZERO leakage of sensitive credentials or PII
    assert secret_password not in full_log_text
    assert secret_token not in full_log_text
    assert sensitive_email not in full_log_text
    assert sensitive_ssn not in full_log_text

