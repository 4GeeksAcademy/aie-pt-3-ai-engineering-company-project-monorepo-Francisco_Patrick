import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_post_telemetry_events_valid_batch():
    payload = {
        "events": [
            {
                "eventId": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_12345",
                "userId": "usr_test_operator",
                "event_type": "inbound_order_created",
                "schemaVersion": "1.0.0",
                "requestId": "req_112233",
                "properties": {
                    "inboundOrderId": "INB-001",
                    "warehouseCode": "LA-01",
                    "totalSkus": 3,
                    "totalUnits": 50,
                },
            },
            {
                "eventId": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_12345",
                "userId": None,
                "event_type": "stock_threshold_triggered",
                "schemaVersion": "1.0.0",
                "requestId": "req_112234",
                "properties": {
                    "skuId": "SKU-99",
                    "triggerSeverity": "WARNING",
                },
            },
        ]
    }

    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 2
    assert data["stored"] == 2
    assert data["rejected"] == 0


def test_post_telemetry_events_mixed_batch_partial_persistence():
    """T011: API integration test for mixed batch ingestion returning HTTP 200 OK with { "received": 5, "stored": 3, "rejected": 2 }."""
    valid_id_1 = str(uuid.uuid4())
    valid_id_2 = str(uuid.uuid4())
    valid_id_3 = str(uuid.uuid4())

    payload = {
        "events": [
            {
                "eventId": valid_id_1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_mixed_1",
                "userId": "usr_test_1",
                "event_type": "inbound_order_created",
                "schemaVersion": "1.0.0",
                "requestId": "req_mix_1",
                "properties": {"orderId": "INB-101"},
            },
            {
                # Malformed item 1: non-snake_case event_type
                "eventId": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_mixed_2",
                "event_type": "INVALID_EVENT_TYPE",
                "schemaVersion": "1.0.0",
                "requestId": "req_mix_2",
            },
            {
                "eventId": valid_id_2,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_mixed_3",
                "userId": None,
                "event_type": "stock_exit_recorded",
                "schemaVersion": "1.0.0",
                "requestId": "req_mix_3",
                "properties": {"units": 12},
            },
            {
                # Malformed item 2: missing required eventId and sessionId
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "frontend_error_captured",
                "schemaVersion": "1.0.0",
                "requestId": "req_mix_4",
            },
            {
                "eventId": valid_id_3,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_mixed_5",
                "userId": "usr_test_5",
                "event_type": "auth_login_failed",
                "schemaVersion": "1.0.0",
                "requestId": "req_mix_5",
                "properties": {"reason": "bad_password"},
            },
        ]
    }

    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 5
    assert data["stored"] == 3
    assert data["rejected"] == 2


def test_post_telemetry_events_all_malformed_batch():
    """T012: API integration test for 100% malformed batch committing zero database writes and returning { "received": N, "stored": 0, "rejected": N }."""
    payload = {
        "events": [
            {
                # Malformed 1: bad UUID
                "eventId": "not-a-valid-uuid",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_bad_1",
                "event_type": "inbound_order_created",
                "schemaVersion": "1.0.0",
                "requestId": "req_bad_1",
            },
            {
                # Malformed 2: empty object
                "invalid": "structure",
            },
        ]
    }

    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 2
    assert data["stored"] == 0
    assert data["rejected"] == 2


def test_post_telemetry_events_empty_batch():
    """T016 [US2]: API test confirming empty batch {"events": []} returns HTTP 200 OK with { "received": 0, "stored": 0, "rejected": 0 }."""
    payload = {"events": []}
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 0
    assert data["stored"] == 0
    assert data["rejected"] == 0


def test_post_telemetry_events_missing_envelope_rejected():
    """T017 [US2]: Request completely missing events field returns HTTP 422 Unprocessable Entity."""
    payload = {}
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 422


def test_post_telemetry_events_non_list_events_rejected():
    """T017 [US2]: Request with non-list events payload returns HTTP 422 Unprocessable Entity."""
    for invalid_payload in [
        {"events": "not_a_list"},
        {"events": 123},
        {"events": None},
        {"events": True},
    ]:
        response = client.post("/telemetry/events", json=invalid_payload)
        assert response.status_code == 422, f"Expected 422 for payload {invalid_payload}"


def test_post_telemetry_events_extra_envelope_fields_rejected():
    """T017 [US2]: Extra fields on outer envelope return HTTP 422 Unprocessable Entity."""
    payload = {
        "events": [],
        "unvettedEnvelopeField": "illegal",
    }
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 422


def test_telemetry_endpoint_alias():
    """T018 [US2]: Canonical alias /api/v1/telemetry/events shares identical behavior with /telemetry/events."""
    def _create_valid_event():
        return {
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sessionId": "sess_alias_shared",
            "userId": "usr_alias",
            "event_type": "inbound_order_created",
            "schemaVersion": "1.0.0",
            "requestId": f"req_{uuid.uuid4().hex[:8]}",
            "properties": {"inboundOrderId": "INB-ALIAS-1"},
        }

    def _create_malformed_event():
        return {
            "eventId": "not-a-uuid",
            "timestamp": "invalid-time",
            "sessionId": "",
            "event_type": "INVALID_EVENT",
        }

    # 1. Valid batch matches between alias and legacy
    res_v1 = client.post("/api/v1/telemetry/events", json={"events": [_create_valid_event()]})
    res_legacy = client.post("/telemetry/events", json={"events": [_create_valid_event()]})
    assert res_v1.status_code == res_legacy.status_code == 200
    assert res_v1.json() == res_legacy.json() == {"received": 1, "stored": 1, "rejected": 0}

    # 2. Empty batch matches
    res_v1_empty = client.post("/api/v1/telemetry/events", json={"events": []})
    res_legacy_empty = client.post("/telemetry/events", json={"events": []})
    assert res_v1_empty.status_code == res_legacy_empty.status_code == 200
    assert res_v1_empty.json() == res_legacy_empty.json() == {"received": 0, "stored": 0, "rejected": 0}

    # 3. Mixed batch matches
    res_v1_mixed = client.post(
        "/api/v1/telemetry/events",
        json={"events": [_create_valid_event(), _create_malformed_event()]},
    )
    res_legacy_mixed = client.post(
        "/telemetry/events",
        json={"events": [_create_valid_event(), _create_malformed_event()]},
    )
    assert res_v1_mixed.status_code == res_legacy_mixed.status_code == 200
    assert res_v1_mixed.json() == res_legacy_mixed.json() == {"received": 2, "stored": 1, "rejected": 1}

    # 4. Invalid outer envelope matches
    res_v1_bad = client.post("/api/v1/telemetry/events", json={})
    res_legacy_bad = client.post("/telemetry/events", json={})
    assert res_v1_bad.status_code == res_legacy_bad.status_code == 422

    res_v1_extra = client.post(
        "/api/v1/telemetry/events",
        json={"events": [], "unvettedEnvelopeField": "illegal"},
    )
    res_legacy_extra = client.post(
        "/telemetry/events",
        json={"events": [], "unvettedEnvelopeField": "illegal"},
    )
    assert res_v1_extra.status_code == res_legacy_extra.status_code == 422
