"""Automated test suite for Real-Time RFP Ticket Notifications (SSE Part 1 of 2).

Covers:
- User Story 1 (T008): SSE stream headers (`Content-Type: text/event-stream`, `Cache-Control: no-cache`,
  `Connection: keep-alive`, `X-Accel-Buffering: no`), named `event: rfp_ticket_created` wire framing,
  flat JSON payload schema validation, non-LLM `POST /api/v1/rfp/tickets` broadcast, intake pipeline
  orchestrate broadcast, and multi-client concurrent fan-out.
- User Story 2 (T017): Unauthenticated (`401`), invalid/expired JWT (`401`), and inactive user (`403`)
  rejection on `/api/v1/rfp/notifications/stream` and `/api/v1/rfp/events`, periodic `: keep-alive`
  comment frame emission during idle periods, and subscriber queue cleanup on disconnect.
- User Story 3 (T022): Monotonic SSE `id:` sequence assignment, `Last-Event-ID` header and
  `last_event_id` query parameter ring-buffer replay (`id > last_event_id`), broadcaster `ticket_id`
  deduplication, and enriched `GET /api/v1/rfp/tickets` reconciliation fields (`rfp_id`,
  `client_country`, `services_requested`).
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlmodel import Session

from data.pipelines.rfp_intake.rfp_intake_pipeline import RFPIntakePipeline, create_initial_state
from data.pipelines.rfp_intake.rfp_orchestrator_agent import ExtractedMetadataResult
from domain.rfp.entities import IntakeTicket, RFPTicketCreatedEvent
from infrastructure.messaging.rfp_notification_broadcaster import (
    RFPNotificationBroadcaster,
    get_rfp_notification_broadcaster_singleton,
)
from infrastructure.persistence.sqlmodel.client import get_engine
from infrastructure.persistence.sqlmodel.rfp_repository import SQLModelIntakeTicketRepository


@pytest.fixture(autouse=True)
def reset_rfp_broadcaster() -> Any:
    """Reset the singleton SSE broadcaster before and after every test for deterministic isolation."""
    broadcaster = get_rfp_notification_broadcaster_singleton()
    broadcaster.reset()
    yield broadcaster
    broadcaster.reset()


def _parse_sse_wire_text(raw_text: str) -> List[Dict[str, Any]]:
    """Parse raw W3C Server-Sent Events wire text into structured frames (events and comments)."""
    frames: List[Dict[str, Any]] = []
    blocks = [b for b in raw_text.split("\n\n") if b.strip()]
    for block in blocks:
        lines = block.splitlines()
        if all(line.startswith(":") for line in lines):
            frames.append({"type": "comment", "raw": block.strip()})
            continue

        frame: Dict[str, Any] = {"type": "event", "id": None, "event": "message", "data": ""}
        data_lines: List[str] = []
        for line in lines:
            if line.startswith(":"):
                continue
            if line.startswith("id:"):
                frame["id"] = line.removeprefix("id:").strip()
            elif line.startswith("event:"):
                frame["event"] = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        frame["data"] = "\n".join(data_lines)
        frames.append(frame)
    return frames


def _load_event_json_schema() -> Dict[str, Any]:
    """Load the canonical rfp-ticket-created-event.schema.json contract."""
    repo_root = Path(__file__).resolve().parents[3]
    schema_path = (
        repo_root
        / "specs"
        / "034-sse-rfp-notifications"
        / "contracts"
        / "rfp-ticket-created-event.schema.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


# =====================================================================
# User Story 1: Real-Time New RFP Ticket Arrival (T008)
# =====================================================================


def test_us1_post_rfp_tickets_registers_analyzing_ticket_and_emits_flat_sse_event(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify POST /api/v1/rfp/tickets persists a ticket with status=analyzing and broadcasts rfp_ticket_created."""
    token = test_users["active_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "ticket_id": "tkt_0225",
        "rfp_id": "rfp_0071",
        "client_name": "Northline Apparel",
        "client_country": "US",
        "services_requested": ["warehouse", "lastmile"],
        "monthly_volume": 45000,
        "deadline": "2026-08-15",
        "budget_range": "$150,000 - $200,000 / month",
    }

    create_resp = client.post("/api/v1/rfp/tickets", json=payload, headers=headers)
    assert create_resp.status_code == 201
    created_body = create_resp.json()

    # Validate against contract schema fields
    contract_schema = _load_event_json_schema()
    required_keys = set(contract_schema["required"])
    assert set(created_body.keys()) == required_keys
    assert created_body["ticket_id"] == "tkt_0225"
    assert created_body["rfp_id"] == "rfp_0071"
    assert created_body["client_name"] == "Northline Apparel"
    assert created_body["client_country"] == "US"
    assert created_body["services_requested"] == ["warehouse", "lastmile"]
    assert created_body["status"] == "analyzing"
    assert created_body["created_at"].endswith("Z")

    # Connect to SSE stream with Last-Event-ID=0 and max_events=1 to inspect the exact wire frame
    with client.stream(
        "GET",
        "/api/v1/rfp/notifications/stream?last_event_id=0&max_events=1",
        headers=headers,
    ) as stream_resp:
        assert stream_resp.status_code == 200
        assert stream_resp.headers["content-type"].startswith("text/event-stream")
        assert stream_resp.headers.get("cache-control") == "no-cache"
        assert stream_resp.headers.get("connection") == "keep-alive"
        assert stream_resp.headers.get("x-accel-buffering") == "no"

        raw_wire = "".join(stream_resp.iter_text())

    frames = _parse_sse_wire_text(raw_wire)
    assert len(frames) == 1
    event_frame = frames[0]
    assert event_frame["type"] == "event"
    assert event_frame["id"] == "1"
    assert event_frame["event"] == "rfp_ticket_created"

    # Must be flat JSON in data: (NOT wrapped in {"event": ..., "data": ...})
    parsed_data = json.loads(event_frame["data"])
    assert "event" not in parsed_data
    assert "data" not in parsed_data
    assert set(parsed_data.keys()) == required_keys
    assert parsed_data["ticket_id"] == "tkt_0225"
    assert parsed_data["rfp_id"] == "rfp_0071"
    assert parsed_data["client_name"] == "Northline Apparel"
    assert parsed_data["client_country"] == "US"
    assert parsed_data["services_requested"] == ["warehouse", "lastmile"]
    assert parsed_data["status"] == "analyzing"


def test_us1_legacy_and_alias_sse_routes_emit_identical_frames(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify legacy /rfp/notifications/stream and alias /api/v1/rfp/events work identically."""
    token = test_users["active_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/rfp/tickets",
        json={
            "ticket_id": "tkt_0301",
            "rfp_id": "rfp_0099",
            "client_name": "Iberia Retail Logistics",
            "client_country": "ES",
            "services_requested": ["warehouse", "reverse"],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201

    for route in (
        "/rfp/notifications/stream?last_event_id=0&max_events=1",
        "/api/v1/rfp/events?last_event_id=0&max_events=1",
        "/rfp/events?last_event_id=0&max_events=1",
    ):
        with client.stream("GET", route, headers=headers) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            frames = _parse_sse_wire_text("".join(resp.iter_text()))
            assert len(frames) == 1
            assert frames[0]["event"] == "rfp_ticket_created"
            payload = json.loads(frames[0]["data"])
            assert payload["ticket_id"] == "tkt_0301"
            assert payload["client_country"] == "ES"


def test_us1_multi_client_concurrent_fan_out() -> None:
    """Verify multiple connected commercial users receive the same rfp_ticket_created notification concurrently."""

    async def _run_concurrent_fanout() -> None:
        broadcaster = RFPNotificationBroadcaster()
        queues = [broadcaster.subscribe() for _ in range(5)]
        assert broadcaster.active_subscriber_count == 5

        event = RFPTicketCreatedEvent(
            ticket_id="tkt_0225",
            rfp_id="rfp_0071",
            client_name="Northline Apparel",
            client_country="US",
            services_requested=["warehouse", "lastmile"],
            status="analyzing",
            created_at="2026-07-24T14:32:00Z",
        )
        envelope = broadcaster.publish_ticket_created(event)
        assert envelope is not None
        assert envelope.event_id == 1

        received = await asyncio.gather(*(q.get() for q in queues))
        for env in received:
            assert env.event_id == 1
            assert env.event_name == "rfp_ticket_created"
            assert env.payload.ticket_id == "tkt_0225"
            assert env.payload.client_name == "Northline Apparel"

        for q in queues:
            broadcaster.unsubscribe(q)
        assert broadcaster.active_subscriber_count == 0

    asyncio.run(_run_concurrent_fanout())


def test_us1_intake_pipeline_orchestrate_node_emits_rfp_ticket_created() -> None:
    """Verify RFPIntakePipeline._node_orchestrate broadcasts rfp_ticket_created when metadata is saved."""
    broadcaster = RFPNotificationBroadcaster()
    subscriber_queue = broadcaster.subscribe()

    with Session(get_engine()) as session:
        repo = SQLModelIntakeTicketRepository(session)
        ticket = IntakeTicket.create(
            raw_pdf_path="/tmp/sample_rfp.pdf",
            raw_pdf_filename="sample_rfp.pdf",
            file_size_bytes=2048,
            ticket_number="rfp_0088",
            ticket_id=uuid4(),
        )
        repo.save_ticket(ticket)

        pipeline = RFPIntakePipeline(repository=repo, broadcaster=broadcaster)
        pipeline.orchestrator.extract = MagicMock(  # type: ignore[method-assign]
            return_value=ExtractedMetadataResult(
                client_name="Mediterranean Goods S.L.",
                client_country="ES",
                currency="EUR",
                services_requested=["warehouse", "lastmile"],
                monthly_volume=12000,
                deadline="2026-09-01",
                budget_range="EUR 80,000",
                departments_needed=["warehouse", "lastmile"],
                unsupported_services=[],
            )
        )

        state = create_initial_state(ticket.id, "/tmp/sample_rfp.pdf")
        state["is_rfp"] = True
        state["markdown_content"] = "# RFP Mediterranean Goods"
        pipeline._node_orchestrate(state)

    assert not subscriber_queue.empty()
    envelope = subscriber_queue.get_nowait()
    assert envelope.event_name == "rfp_ticket_created"
    flat = envelope.payload.to_flat_dict()
    assert flat["ticket_id"] == str(ticket.id)
    assert flat["rfp_id"] == "rfp_0088"
    assert flat["client_name"] == "Mediterranean Goods S.L."
    assert flat["client_country"] == "ES"
    assert flat["services_requested"] == ["warehouse", "lastmile"]
    assert flat["status"] == "analyzing"


# =====================================================================
# User Story 2: Authenticated Stream Access & Idle Stability (T017)
# =====================================================================


def test_us2_unauthenticated_and_invalid_token_requests_are_rejected_before_streaming(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify unauthenticated, malformed, expired, and inactive-user requests fail with 401/403 and zero events."""
    # 1. Missing Authorization header -> 401
    resp_no_auth = client.get("/api/v1/rfp/notifications/stream")
    assert resp_no_auth.status_code == 401

    resp_alias_no_auth = client.get("/api/v1/rfp/events")
    assert resp_alias_no_auth.status_code == 401

    # 2. Invalid JWT token -> 401
    resp_bad_token = client.get(
        "/api/v1/rfp/notifications/stream",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp_bad_token.status_code == 401

    # 3. Expired JWT token -> 401
    resp_expired = client.get(
        "/api/v1/rfp/notifications/stream",
        headers={"Authorization": f"Bearer {test_users['expired_token']}"},
    )
    assert resp_expired.status_code == 401

    # 4. Inactive user token -> 403
    inactive_token = client.app.dependency_overrides[
        list(client.app.dependency_overrides.keys())[0]
    ]().create_access_token(subject=test_users["inactive"].id)
    resp_inactive = client.get(
        "/api/v1/rfp/notifications/stream",
        headers={"Authorization": f"Bearer {inactive_token}"},
    )
    assert resp_inactive.status_code == 403


def test_us2_periodic_keep_alive_heartbeat_and_clean_subscriber_teardown(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify idle SSE stream emits `: keep-alive` comment frames and unsubscribes cleanly on close."""
    broadcaster = get_rfp_notification_broadcaster_singleton()
    assert broadcaster.active_subscriber_count == 0

    token = test_users["active_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with client.stream(
        "GET",
        "/api/v1/rfp/notifications/stream?heartbeat_interval=0.05&max_events=2",
        headers=headers,
    ) as stream_resp:
        assert stream_resp.status_code == 200
        raw_wire = "".join(stream_resp.iter_text())

    frames = _parse_sse_wire_text(raw_wire)
    assert len(frames) == 2
    assert all(f["type"] == "comment" and f["raw"] == ": keep-alive" for f in frames)

    # Subscriber queue must be cleaned up when stream exits
    assert broadcaster.active_subscriber_count == 0


# =====================================================================
# User Story 3: Reconnection Replay, Recovery & Deduplication (T022)
# =====================================================================


def test_us3_last_event_id_ring_buffer_replay_and_deduplication(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify monotonic SSE IDs, Last-Event-ID replay (id > last_event_id), and ticket_id deduplication."""
    token = test_users["active_token"]
    headers = {"Authorization": f"Bearer {token}"}

    tickets_to_create = [
        {
            "ticket_id": "tkt_0101",
            "rfp_id": "rfp_0011",
            "client_name": "Alpha Logistics",
            "client_country": "US",
            "services_requested": ["warehouse"],
        },
        {
            "ticket_id": "tkt_0102",
            "rfp_id": "rfp_0012",
            "client_name": "Beta Freight",
            "client_country": "ES",
            "services_requested": ["lastmile"],
        },
        {
            "ticket_id": "tkt_0103",
            "rfp_id": "rfp_0013",
            "client_name": "Gamma Returns",
            "client_country": "US",
            "services_requested": ["reverse"],
        },
    ]

    for item in tickets_to_create:
        r = client.post("/api/v1/rfp/tickets", json=item, headers=headers)
        assert r.status_code == 201

    # Duplicate publication of tkt_0102 must be ignored by broadcaster deduplication
    broadcaster = get_rfp_notification_broadcaster_singleton()
    dup_result = broadcaster.publish_ticket_created(
        RFPTicketCreatedEvent(
            ticket_id="tkt_0102",
            rfp_id="rfp_0012",
            client_name="Beta Freight",
            client_country="ES",
            services_requested=["lastmile"],
        )
    )
    assert dup_result is None

    # Reconnect passing Last-Event-ID: 1 header -> should replay events 2 and 3 only
    replay_headers = {
        "Authorization": f"Bearer {token}",
        "Last-Event-ID": "1",
    }
    with client.stream(
        "GET",
        "/api/v1/rfp/notifications/stream?max_events=2",
        headers=replay_headers,
    ) as stream_resp:
        assert stream_resp.status_code == 200
        raw_wire = "".join(stream_resp.iter_text())

    frames = _parse_sse_wire_text(raw_wire)
    assert len(frames) == 2
    assert [f["id"] for f in frames] == ["2", "3"]
    assert [json.loads(f["data"])["ticket_id"] for f in frames] == ["tkt_0102", "tkt_0103"]


def test_us3_get_tickets_reconciliation_includes_enriched_briefing_fields(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify GET /api/v1/rfp/tickets returns rfp_id, client_country, and services_requested for client reconciliation."""
    token = test_users["active_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/v1/rfp/tickets",
        json={
            "ticket_id": "tkt_0225",
            "rfp_id": "rfp_0071",
            "client_name": "Northline Apparel",
            "client_country": "US",
            "services_requested": ["warehouse", "lastmile"],
        },
        headers=headers,
    )

    list_resp = client.get("/api/v1/rfp/tickets?limit=20", headers=headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] >= 1

    matching = [item for item in body["items"] if item["ticket_id"] == "tkt_0225"]
    assert len(matching) == 1
    summary = matching[0]
    assert summary["rfp_id"] == "rfp_0071"
    assert summary["client_name"] == "Northline Apparel"
    assert summary["client_country"] == "US"
    assert summary["services_requested"] == ["warehouse", "lastmile"]
    assert summary["status"] == "analizando"
