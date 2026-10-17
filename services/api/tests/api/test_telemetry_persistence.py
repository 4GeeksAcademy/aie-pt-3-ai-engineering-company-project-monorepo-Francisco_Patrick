"""Integration and immutability tests for persistent telemetry storage.

Validates User Story 3:
- T021: Persistent database storage and direct query retrieval of business and technical events.
- T022: Immutability tests asserting SQLModelTelemetrySink, domain ports, and endpoints provide no UPDATE or DELETE capabilities.
"""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from main import app
from infrastructure.database import engine
from infrastructure.persistence.sqlmodel.models import TelemetryEventRecord
from infrastructure.persistence.sqlmodel.telemetry_sink import SQLModelTelemetrySink
from domain.telemetry.models import TelemetryEvent
from domain.telemetry.ports import TelemetrySinkPort

client = TestClient(app)


def test_t021_business_and_technical_events_persistence_and_query_retrieval():
    """T021 [US3]: Ingest business and technical events and verify persistent DB storage and retrieval."""
    event_id_business_1 = uuid.uuid4()
    event_id_business_2 = uuid.uuid4()
    event_id_tech_1 = uuid.uuid4()
    event_id_tech_2 = uuid.uuid4()

    now_utc = datetime.now(timezone.utc)

    payload = {
        "events": [
            # 1. Business event: inbound_order_created
            {
                "eventId": str(event_id_business_1),
                "timestamp": now_utc.isoformat(),
                "sessionId": "sess_audit_001",
                "userId": "usr_warehouse_lead",
                "event_type": "inbound_order_created",
                "schemaVersion": "1.0.0",
                "requestId": "req_trace_001",
                "properties": {
                    "inboundOrderId": "INB-9988",
                    "warehouseCode": "WH-NORTH",
                    "lineItemsCount": 4,
                    "isExpedited": True,
                    "nestedDetails": {"supplierId": "SUP-42", "priority": "HIGH"},
                },
            },
            # 2. Business event: stock_exit_recorded
            {
                "eventId": str(event_id_business_2),
                "timestamp": now_utc.isoformat(),
                "sessionId": "sess_audit_001",
                "userId": None,  # unauthenticated or system actor
                "event_type": "stock_exit_recorded",
                "schemaVersion": "1.0.0",
                "requestId": "req_trace_002",
                "properties": {
                    "sku": "SKU-PROD-77",
                    "quantity": 15,
                    "destination": "OUT-DOCK-B",
                },
            },
            # 3. Technical observability event: auth_login_failed
            {
                "eventId": str(event_id_tech_1),
                "timestamp": now_utc.isoformat(),
                "sessionId": "sess_audit_002",
                "userId": "usr_masked_attempt",
                "event_type": "auth_login_failed",
                "schemaVersion": "1.0.0",
                "requestId": "req_trace_003",
                "properties": {
                    "attemptCount": 3,
                    "ipAddress": "10.0.0.1",
                    "reason": "invalid_credentials",
                },
            },
            # 4. Technical observability event: frontend_error_captured
            {
                "eventId": str(event_id_tech_2),
                "timestamp": now_utc.isoformat(),
                "sessionId": "sess_audit_002",
                "userId": None,
                "event_type": "frontend_error_captured",
                "schemaVersion": "1.0.0",
                "requestId": "req_trace_004",
                "properties": {
                    "component": "OrderTable",
                    "errorName": "TypeError",
                    "handled": False,
                },
            },
        ]
    }

    # Ingest through HTTP endpoint
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    receipt = response.json()
    assert receipt["received"] == 4
    assert receipt["stored"] == 4
    assert receipt["rejected"] == 0

    # Query persistent database directly using SQLModel session
    with Session(engine) as session:
        statement = select(TelemetryEventRecord).where(
            TelemetryEventRecord.session_id.in_(["sess_audit_001", "sess_audit_002"])
        )
        persisted_records = session.exec(statement).all()
        assert len(persisted_records) == 4

        record_map = {r.event_id: r for r in persisted_records}

        # Verify business event 1
        rec1 = record_map[event_id_business_1]
        assert rec1.event_type == "inbound_order_created"
        assert rec1.session_id == "sess_audit_001"
        assert rec1.user_id == "usr_warehouse_lead"
        assert rec1.schema_version == "1.0.0"
        assert rec1.request_id == "req_trace_001"
        assert rec1.properties["inboundOrderId"] == "INB-9988"
        assert rec1.properties["isExpedited"] is True
        assert rec1.properties["nestedDetails"]["supplierId"] == "SUP-42"
        assert rec1.created_at is not None

        # Verify business event 2
        rec2 = record_map[event_id_business_2]
        assert rec2.event_type == "stock_exit_recorded"
        assert rec2.session_id == "sess_audit_001"
        assert rec2.user_id is None
        assert rec2.properties["quantity"] == 15

        # Verify technical observability event 1
        rec3 = record_map[event_id_tech_1]
        assert rec3.event_type == "auth_login_failed"
        assert rec3.user_id == "usr_masked_attempt"
        assert rec3.properties["reason"] == "invalid_credentials"

        # Verify technical observability event 2
        rec4 = record_map[event_id_tech_2]
        assert rec4.event_type == "frontend_error_captured"
        assert rec4.properties["component"] == "OrderTable"
        assert rec4.properties["handled"] is False


def test_t021_cross_dialect_json_and_alias_endpoint():
    """T021 [US3]: Ingest via /api/v1/telemetry/events with complex nested JSON and verify direct query retrieval."""
    event_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)

    complex_properties = {
        "metadata": {
            "tags": ["critical", "inventory", "sync"],
            "metrics": {"durationMs": 142.5, "retryCount": 0},
            "enabled": True,
            "nullableField": None,
        },
        "items": [
            {"sku": "SKU-A", "quantity": 10},
            {"sku": "SKU-B", "quantity": 20},
        ],
    }

    payload = {
        "events": [
            {
                "eventId": str(event_id),
                "timestamp": now_utc.isoformat(),
                "sessionId": "sess_alias_complex",
                "userId": "usr_sync_agent",
                "event_type": "inbound_order_created",
                "schemaVersion": "1.0.0",
                "requestId": "req_alias_001",
                "properties": complex_properties,
            }
        ]
    }

    response = client.post("/api/v1/telemetry/events", json=payload)
    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 1, "rejected": 0}

    with Session(engine) as session:
        record = session.get(TelemetryEventRecord, event_id)
        assert record is not None
        assert record.event_type == "inbound_order_created"
        assert record.properties == complex_properties
        assert record.properties["metadata"]["tags"] == ["critical", "inventory", "sync"]
        assert record.properties["metadata"]["metrics"]["durationMs"] == 142.5
        assert record.properties["items"][1]["sku"] == "SKU-B"


def test_t021_sink_direct_atomic_persistence_and_rollback():
    """T021 [US3]: Test direct SQLModelTelemetrySink atomic record_events commit and transaction rollback on error."""
    sink = SQLModelTelemetrySink()

    event1 = TelemetryEvent(
        event_id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        session_id="sess_direct_1",
        user_id="usr_direct",
        event_type="inbound_order_created",
        schema_version="1.0.0",
        request_id="req_dir_1",
        properties={"order": 1},
    )
    event2 = TelemetryEvent(
        event_id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        session_id="sess_direct_2",
        user_id=None,
        event_type="stock_exit_recorded",
        schema_version="1.0.0",
        request_id="req_dir_2",
        properties={"order": 2},
    )

    count = sink.record_events([event1, event2])
    assert count == 2

    with Session(engine) as session:
        r1 = session.get(TelemetryEventRecord, event1.eventId)
        r2 = session.get(TelemetryEventRecord, event2.eventId)
        assert r1 is not None
        assert r2 is not None
        assert r1.properties == {"order": 1}
        assert r2.properties == {"order": 2}

    # Verify atomic rollback on primary key conflict / duplicate
    duplicate_event = TelemetryEvent(
        event_id=event1.eventId,  # Duplicate PK
        timestamp=datetime.now(timezone.utc),
        session_id="sess_duplicate",
        user_id="usr_dup",
        event_type="auth_login_failed",
        schema_version="1.0.0",
        request_id="req_dup",
        properties={"dup": True},
    )
    new_event = TelemetryEvent(
        event_id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        session_id="sess_new_failed",
        user_id="usr_new",
        event_type="inbound_order_created",
        schema_version="1.0.0",
        request_id="req_new",
        properties={"new": True},
    )

    with pytest.raises(Exception):
        sink.record_events([new_event, duplicate_event])

    # Assert new_event was NOT committed (atomic rollback succeeded)
    with Session(engine) as session:
        failed_record = session.get(TelemetryEventRecord, new_event.eventId)
        assert failed_record is None


def test_t022_immutability_sink_and_domain_ports_provide_no_mutation_capabilities():
    """T022 [US3]: Assert TelemetrySinkPort and SQLModelTelemetrySink provide zero UPDATE or DELETE methods."""
    prohibited_method_substrings = ["update", "delete", "remove", "modify", "patch", "put"]

    # 1. Domain Port check
    port_methods = [m for m in dir(TelemetrySinkPort) if not m.startswith("_")]
    for method_name in port_methods:
        for prohibited in prohibited_method_substrings:
            assert prohibited not in method_name.lower(), (
                f"TelemetrySinkPort exposes prohibited mutation method: {method_name}"
            )

    # 2. SQLModel Persistence Adapter check
    sink_methods = [m for m in dir(SQLModelTelemetrySink) if not m.startswith("_")]
    for method_name in sink_methods:
        for prohibited in prohibited_method_substrings:
            assert prohibited not in method_name.lower(), (
                f"SQLModelTelemetrySink exposes prohibited mutation method: {method_name}"
            )

    # 3. Explicitly verify calling non-existent mutation methods raises AttributeError
    sink = SQLModelTelemetrySink()
    with pytest.raises(AttributeError):
        getattr(sink, "update_event")
    with pytest.raises(AttributeError):
        getattr(sink, "delete_event")
    with pytest.raises(AttributeError):
        getattr(sink, "delete_batch")
    with pytest.raises(AttributeError):
        getattr(sink, "modify_record")


def test_t022_immutability_http_endpoints_reject_update_and_delete_methods():
    """T022 [US3]: Assert HTTP endpoints reject PUT, PATCH, and DELETE with 405 Method Not Allowed."""
    for path in ["/telemetry/events", "/api/v1/telemetry/events"]:
        res_put = client.put(path, json={"events": []})
        assert res_put.status_code == 405, f"PUT {path} should return 405 Method Not Allowed"

        res_patch = client.patch(path, json={"events": []})
        assert res_patch.status_code == 405, f"PATCH {path} should return 405 Method Not Allowed"

        res_delete = client.delete(path)
        assert res_delete.status_code == 405, f"DELETE {path} should return 405 Method Not Allowed"
