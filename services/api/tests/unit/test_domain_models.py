"""Unit tests for pure domain models and business invariants.

Verifies domain models operate with zero database or framework coupling,
and enforces critical business validation rules and state machine transitions.
"""

from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError

from domain.auth.models import PasswordResetToken, Profile, User
from domain.common.exceptions import InvalidStatusTransitionError
from domain.incidents.models import Incident
from domain.inventory.models import SKU, InventoryProduct, StockEntry, StockExit
from domain.suppliers.models import Supplier
from domain.telemetry.models import TelemetryBatch, TelemetryEvent


# --- Supplier Domain Model Tests ---
def test_supplier_creation_valid():
    """Happy Path: Supplier domain entity initializes with valid fields."""
    supplier = Supplier(
        name="Global Air Cargo",
        country="Germany",
        category="freight",
        cost_per_kg=5.50,
        status="active",
    )
    assert supplier.name == "Global Air Cargo"
    assert supplier.country == "Germany"
    assert supplier.category == "freight"
    assert supplier.categories == ["freight"]
    assert supplier.cost_per_kg == 5.50
    assert supplier.status == "active"


def test_supplier_categories_synchronization():
    """Happy Path: Categories list and category single value synchronize bidirectionally."""
    s1 = Supplier(
        name="Maritime Freight Corp",
        country="Netherlands",
        categories=["ocean_freight", "customs"],
        cost_per_kg=2.75,
    )
    assert s1.category == "ocean_freight"

    s2 = Supplier(
        name="Express Rail",
        country="France",
        category="rail",
        cost_per_kg=3.20,
    )
    assert s2.categories == ["rail"]


def test_supplier_cost_per_kg_must_be_positive():
    """Invariant: Shipping cost per kg <= 0.0 raises ValidationError."""
    with pytest.raises(ValidationError):
        Supplier(
            name="Free Shipping Inc",
            country="Spain",
            category="freight",
            cost_per_kg=0.0,
        )

    with pytest.raises(ValidationError):
        Supplier(
            name="Negative Shipping Inc",
            country="Spain",
            category="freight",
            cost_per_kg=-1.50,
        )


# --- Inventory Domain Model Tests ---
def test_sku_model_validation():
    """Happy Path: SKU model initializes and enforces non-negative threshold."""
    sku = SKU(
        sku="SKU-TEST-001",
        name="Heavy Duty Alternator",
        warehouse_id="wh-central",
        low_stock_threshold=15,
    )
    assert sku.sku == "SKU-TEST-001"
    assert sku.low_stock_threshold == 15

    with pytest.raises(ValidationError):
        SKU(
            sku="SKU-FAIL",
            name="Invalid Threshold SKU",
            warehouse_id="wh-north",
            low_stock_threshold=-5,
        )


def test_stock_entry_and_exit_quantity_invariants():
    """Invariant: Stock transaction quantity must be strictly positive (> 0)."""
    entry = StockEntry(sku_id=1, warehouse_id="wh-central", quantity=100)
    assert entry.quantity == 100

    exit_rec = StockExit(sku_id=1, warehouse_id="wh-central", quantity=25)
    assert exit_rec.quantity == 25

    with pytest.raises(ValidationError):
        StockEntry(sku_id=1, warehouse_id="wh-central", quantity=0)

    with pytest.raises(ValidationError):
        StockExit(sku_id=1, warehouse_id="wh-central", quantity=-10)


def test_inventory_product_projection_is_low_stock():
    """Business Logic: InventoryProduct dynamically calculates is_low_stock."""
    p1 = InventoryProduct(
        id=1,
        sku="SKU-LOW",
        name="Low Stock Filter",
        warehouse_id="wh-east",
        current_stock=5,
        low_stock_threshold=10,
        is_low_stock=True,
    )
    assert p1.is_low_stock is True

    p2 = InventoryProduct(
        id=2,
        sku="SKU-OK",
        name="Healthy Stock Filter",
        warehouse_id="wh-east",
        current_stock=25,
        low_stock_threshold=10,
        is_low_stock=False,
    )
    assert p2.is_low_stock is False


# --- Incident Domain Model & State Transitions ---
def test_incident_creation_and_defaults():
    """Happy Path: Incident domain model creates with default lifecycle status open."""
    incident = Incident(
        title="Forklift collision",
        description="Forklift grazed pallet rack 3",
        category="warehouse",
    )
    assert incident.id.startswith("inc_")
    assert incident.status == "open"
    assert incident.origin == "customer"
    assert incident.branch == "central"


def test_incident_valid_status_transitions():
    """Lifecycle: Allowed status transitions progress cleanly through state machine."""
    inc = Incident(
        title="Late Delivery Route 4",
        description="Driver delayed due to weather",
        category="last_mile",
    )
    assert inc.status == "open"

    # open -> in_progress
    inc.update_status("in_progress")
    assert inc.status == "in_progress"

    # in_progress -> resolved
    inc.update_status("resolved")
    assert inc.status == "resolved"

    # resolved -> closed
    inc.update_status("closed")
    assert inc.status == "closed"


def test_incident_invalid_status_transition_raises():
    """Lifecycle Invariant: Direct transition from open to resolved is prohibited."""
    inc = Incident(
        title="Direct Jump Incident",
        description="Attempting to skip in_progress",
        category="warehouse",
    )
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        inc.update_status("resolved")
    assert "Cannot transition incident status from 'open' to 'resolved'" in str(exc_info.value)


def test_incident_terminal_state_modification_prohibited():
    """Lifecycle Invariant: Modifying terminal closed or discarded incident raises."""
    inc = Incident(
        title="Closed Incident",
        description="Already confirmed closed",
        category="warehouse",
        status="closed",
    )
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        inc.update_status("open")
    assert "Incident is in terminal state 'closed' and cannot be modified" in str(exc_info.value)


def test_incident_satisfaction_index_bounds():
    """Invariant: Satisfaction index must fall within [1.0, 5.0]."""
    valid_inc = Incident(
        title="Rated Incident",
        description="Customer gave feedback",
        category="customer_experience",
        satisfaction_index=4.5,
    )
    assert valid_inc.satisfaction_index == 4.5

    with pytest.raises(ValidationError):
        Incident(
            title="Overrated Incident",
            description="Score over 5.0",
            category="customer_experience",
            satisfaction_index=5.5,
        )

    with pytest.raises(ValidationError):
        Incident(
            title="Underrated Incident",
            description="Score below 1.0",
            category="customer_experience",
            satisfaction_index=0.5,
        )


# --- Auth Domain Models ---
def test_user_and_profile_models():
    """Happy Path: User and Profile domain models initialize cleanly."""
    user = User(
        id="usr_abc123",
        email="operator@trackflow.com",
        hashed_password="bcrypt_hashed_string",
        role="user",
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    assert user.id == "usr_abc123"
    assert user.email == "operator@trackflow.com"
    assert user.is_active is True

    profile = Profile(
        user_id="usr_abc123",
        name="Sarah Connor",
        phone="+1234567890",
    )
    assert profile.user_id == "usr_abc123"
    assert profile.name == "Sarah Connor"


def test_password_reset_token_is_used_property():
    """Value Object: PasswordResetToken.is_used tracks used_at timestamp presence."""
    token = PasswordResetToken(
        id="tok_1",
        user_id="usr_abc123",
        token_hash="hash123",
        expires_at=datetime.now(timezone.utc).isoformat(),
        used_at=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    assert token.is_used is False

    token.used_at = datetime.now(timezone.utc).isoformat()
    assert token.is_used is True


# --- Telemetry Domain Models ---
def test_telemetry_event_envelope_validation():
    """Happy Path: TelemetryEvent conforms strictly to schema and forbids extra attributes."""
    event_id = uuid.uuid4()
    event = TelemetryEvent(
        eventId=event_id,
        timestamp=datetime.now(timezone.utc),
        sessionId="sess_12345",
        event_type="inbound_order_created",
        schemaVersion="1.0.0",
        requestId="req_987",
        properties={"units": 50},
    )
    assert event.eventId == event_id
    assert event.event_type == "inbound_order_created"

    batch = TelemetryBatch(events=[event])
    assert len(batch.events) == 1

    # Forbid extra fields
    with pytest.raises(ValidationError):
        TelemetryEvent(
            eventId=uuid.uuid4(),
            timestamp=datetime.now(timezone.utc),
            sessionId="sess_1",
            event_type="inbound_order_created",
            schemaVersion="1.0.0",
            requestId="req_1",
            unvettedField="illegal",
        )
