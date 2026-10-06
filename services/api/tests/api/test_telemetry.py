import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_post_telemetry_events_valid_batch():
    payload = {
        "events": [
            {
                "eventId": "550e8400-e29b-41d4-a716-446655440000",
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
                    "totalUnits": 50
                }
            },
            {
                "eventId": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_12345",
                "userId": None,
                "event_type": "stock_threshold_triggered",
                "schemaVersion": "1.0.0",
                "requestId": "req_112234",
                "properties": {
                    "skuId": "SKU-99",
                    "triggerSeverity": "WARNING"
                }
            }
        ]
    }

    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 2

def test_post_telemetry_events_empty_batch_rejected():
    payload = {"events": []}
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code in (400, 422)

def test_post_telemetry_events_missing_envelope_field_rejected():
    payload = {
        "events": [
            {
                # Missing eventId
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_12345",
                "userId": None,
                "event_type": "inbound_order_created",
                "schemaVersion": "1.0.0",
                "requestId": "req_112233",
                "properties": {}
            }
        ]
    }
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code in (400, 422)

def test_post_telemetry_events_invalid_event_type_rejected():
    payload = {
        "events": [
            {
                "eventId": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_12345",
                "userId": None,
                "event_type": "InvalidEventTypeNoSnakeCase",
                "schemaVersion": "1.0.0",
                "requestId": "req_112233",
                "properties": {}
            }
        ]
    }
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code in (400, 422)

def test_post_telemetry_events_extra_envelope_fields_rejected():
    payload = {
        "events": [
            {
                "eventId": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_12345",
                "userId": None,
                "event_type": "inbound_order_created",
                "schemaVersion": "1.0.0",
                "requestId": "req_112233",
                "properties": {},
                "unvettedEnvelopeField": "illegal"
            }
        ]
    }
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code in (400, 422)

def test_telemetry_endpoint_alias():
    payload = {
        "events": [
            {
                "eventId": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_alias",
                "userId": None,
                "event_type": "frontend_error_captured",
                "schemaVersion": "1.0.0",
                "requestId": "req_alias_1",
                "properties": {
                    "errorName": "TypeError"
                }
            }
        ]
    }
    response = client.post("/api/v1/telemetry/events", json=payload)
    assert response.status_code == 200
    assert response.json()["received"] == 1
