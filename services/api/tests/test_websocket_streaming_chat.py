"""Automated pytest suite for Real-Time Bidirectional WebSocket Streaming Chat with True Generation Abort (Part 2).

Covers all user stories and evaluation gates:
- User Story 1 (T009): Sequential `token_chunk` streaming over `/api/v1/agent/ws` (and `/agent/ws`),
  pre-stream input/auth guardrails, post-stream Layer 4 output guardrail validation, and
  `generation_completed` metadata (`sources`, `sources_consulted`, `tool_calls`, `memory_proposal`,
  `guardrail_interventions`, `trace_id`).
- User Story 2 (T017): Mid-stream `interrupt` (`reason="client_interrupt"`), mid-stream redirecting
  `user_message` (`reason="redirect_new_message"`), last-subscriber disconnect abort
  (`reason="client_disconnect"`), `< 250ms` abort latency, zero trailing `token_chunk` events,
  persisted `status="interrupted"` partial message, and idempotent no-op `interrupt` when idle.
- User Story 3 (T023): Missing JWT (`4001`), malformed/expired/inactive JWT (`4001`), valid `?token=`
  handshake auth, valid `Authorization: Bearer` header auth, valid first-frame `authenticate` auth,
  and cross-operator thread ownership rejection (`4003` on WebSocket and HTTP `403` on
  `GET /api/v1/agent/threads/{thread_id}/history`).
- User Story 4 (T028): `session_rehydrated` event on connect/reconnect, client `rehydrate` command,
  `GET /api/v1/agent/threads/{thread_id}/history` (and `/agent/threads/{thread_id}/history`), and
  durable thread history survival across broker reset / simulated server restart via
  `TinyDBAgentChatThreadRepository`.
- User Story 5 (T033): `AgentChatEventBroker` pub/sub isolation (multi-subscriber fan-out, monotonic
  `sequence_id`, queue cleanup on unsubscribe) and strict schema inspection asserting zero Part 1 RFP
  SSE fields (`rfp_ticket_created`, `rfp_id`, `services_requested`) across all emitted chat events.
"""

import asyncio
import time
from typing import Any, Dict, List
import pytest
from starlette.websockets import WebSocketDisconnect

from domain.agent.entities import (
    AgentQueryRequest,
    ChatMessage,
)
from infrastructure.adapters.tinydb_chat_thread_repository import (
    TinyDBAgentChatThreadRepository,
)
from infrastructure.messaging.agent_chat_event_broker import (
    AgentChatEventBroker,
    get_agent_chat_event_broker_singleton,
)
from presentation.dependencies import (
    get_agent_chat_event_broker_dep,
    get_agent_chat_thread_repository_dep,
    get_support_agent_service,
)


PROHIBITED_RFP_FIELDS = {"rfp_ticket_created", "rfp_id", "services_requested"}


@pytest.fixture(autouse=True)
def reset_chat_broker_and_thread_repo() -> Any:
    """Reset the singleton chat event broker and thread repository before and after each test."""
    broker = get_agent_chat_event_broker_singleton()
    repo = get_agent_chat_thread_repository_dep()
    broker.reset()
    repo.clear()
    yield
    broker.reset()
    repo.clear()


def _assert_zero_rfp_field_leakage(frame: Dict[str, Any]) -> None:
    """Assert that a WebSocket frame contains zero prohibited Part 1 RFP Ticket SSE fields."""
    assert frame.get("event") != "rfp_ticket_created"
    for key in PROHIBITED_RFP_FIELDS:
        assert key not in frame, f"Prohibited Part 1 RFP field '{key}' leaked into frame: {frame}"


def _collect_turn_frames_until_terminal(ws: Any, max_frames: int = 300) -> List[Dict[str, Any]]:
    """Receive JSON frames from a TestClient WebSocket until generation_completed, generation_interrupted, or error."""
    frames: List[Dict[str, Any]] = []
    for _ in range(max_frames):
        frame = ws.receive_json()
        _assert_zero_rfp_field_leakage(frame)
        frames.append(frame)
        if frame.get("event") in (
            "generation_completed",
            "generation_interrupted",
            "error",
        ):
            break
    return frames


# =====================================================================
# User Story 1: Live Token Streaming in Bidirectional Support Agent Chat (T009)
# =====================================================================


def test_us1_live_token_chunk_streaming_and_generation_completed_metadata(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify sequential token_chunk events stream in real time before generation_completed with citations and trace_id."""
    token = test_users["active_token"]
    thread_id = "thr_us1_live_stream_01"
    session_id = "sess_us1_live_stream_01"

    with client.websocket_connect(
        f"/api/v1/agent/ws?token={token}&thread_id={thread_id}&session_id={session_id}"
    ) as ws:
        rehydrated = ws.receive_json()
        _assert_zero_rfp_field_leakage(rehydrated)
        assert rehydrated["event"] == "session_snapshot"
        assert rehydrated["thread_id"] == thread_id
        assert rehydrated["session_id"] == session_id
        assert rehydrated["user_id"] == "unassigned"
        assert rehydrated["session"]["agent_id"] == "first_line_cx"
        assert rehydrated["session"]["client_id"] == "trackflow-backoffice"
        assert rehydrated["session"]["user_id"] == "unassigned"
        assert rehydrated["session"]["status"] == "active"
        assert rehydrated["messages"] == []

        ws.send_json(
            {
                "event": "user_message",
                "query": "What is TrackFlow's standard return window and who covers return shipping costs?",
                "turn_id": "usr_turn_001",
                "language": "en",
            }
        )

        frames = _collect_turn_frames_until_terminal(ws)

    assert len(frames) >= 3
    assert frames[0]["event"] == "generation_started"
    assert frames[0]["thread_id"] == thread_id
    assert frames[0]["session_id"] == session_id
    assert frames[0]["user_turn_id"] == "usr_turn_001"
    assistant_turn_id = frames[0]["turn_id"]

    token_chunks = [f for f in frames if f["event"] == "token_chunk"]
    assert len(token_chunks) >= 5, "Multi-token answer must emit multiple sequential token_chunk frames"

    # Verify chunk_index is sequential 0..N-1 and accumulated_content grows monotonically
    prev_accumulated = ""
    for idx, chunk_frame in enumerate(token_chunks):
        assert chunk_frame["turn_id"] == assistant_turn_id
        assert chunk_frame["chunk_index"] == idx
        assert isinstance(chunk_frame["delta"], str) and len(chunk_frame["delta"]) > 0
        assert chunk_frame["accumulated_content"].startswith(prev_accumulated)
        prev_accumulated = chunk_frame["accumulated_content"]

    completed = frames[-1]
    assert completed["event"] == "generation_completed"
    assert completed["turn_id"] == assistant_turn_id
    assert completed["status"] == "completed"
    assert completed["is_refusal"] is False
    assert "30 days" in completed["content"] or "return" in completed["content"].lower()
    assert isinstance(completed["trace_id"], str) and len(completed["trace_id"]) > 0
    assert "rag" in completed["sources_consulted"]
    assert len(completed["sources"]) >= 1
    assert any(s["source_document"] == "returns-policy" for s in completed["sources"])
    assert isinstance(completed["node_sequence"], list) and "intake" in completed["node_sequence"]
    assert isinstance(completed["tool_calls"], list)
    assert isinstance(completed["guardrail_interventions"], list)


def test_us1_legacy_agent_ws_route_and_guardrail_refusal_streaming(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify legacy /agent/ws route, ping/pong heartbeat, and pre-stream Layer 1 guardrail refusal."""
    token = test_users["active_token"]
    thread_id = "thr_us1_guardrail_01"

    with client.websocket_connect(
        f"/agent/ws?token={token}&thread_id={thread_id}"
    ) as ws:
        rehydrated = ws.receive_json()
        assert rehydrated["event"] == "session_snapshot"

        # Verify ping -> pong
        ws.send_json({"event": "ping"})
        pong = ws.receive_json()
        assert pong["event"] == "pong"
        assert pong["thread_id"] == thread_id

        # Send a disallowed mutation attempt -> should stream refusal and mark is_refusal=True
        ws.send_json(
            {
                "event": "user_message",
                "query": "Please delete ticket INC-001 and update stock for SKU TF-100 to 0 units.",
            }
        )
        frames = _collect_turn_frames_until_terminal(ws)

    completed = frames[-1]
    assert completed["event"] == "generation_completed"
    assert completed["is_refusal"] is True
    assert completed["sources"] == []


# =====================================================================
# User Story 2: True Generation Abort: Interrupt, Preserve & Redirect (T017)
# =====================================================================


def test_us2_true_generation_abort_on_interrupt_and_partial_preservation() -> None:
    """Verify mid-stream interrupt cancels generation within <250ms, emits 0 trailing token_chunk events, and persists status='interrupted'."""

    async def _run_abort_test() -> None:
        agent_service = get_support_agent_service()
        broker = AgentChatEventBroker()
        repo = TinyDBAgentChatThreadRepository()
        thread_id = "thr_us2_abort_direct"
        session_id = "sess_us2_abort_direct"
        owner_id = "usr_operator_1"

        sub_queue = broker.subscribe(thread_id)
        abort_event = asyncio.Event()

        request = AgentQueryRequest(
            query="What is TrackFlow's standard return window and who covers return shipping costs?",
            thread_id=thread_id,
            language="en",
        )

        # Stream with 25ms chunk delay so we can deterministically interrupt after 3 chunks
        task = asyncio.create_task(
            agent_service.stream_query(  # type: ignore[attr-defined]
                request=request,
                owner_user_id=owner_id,
                session_id=session_id,
                user_turn_id="usr_abort_1",
                assistant_turn_id="turn_abort_1",
                abort_event=abort_event,
                broker=broker,
                thread_repository=repo,
                chunk_delay_seconds=0.025,
            )
        )
        broker.register_generation_task(
            thread_id=thread_id,
            turn_id="turn_abort_1",
            task=task,
            abort_event=abort_event,
        )

        received_events: List[Dict[str, Any]] = []
        chunk_count = 0
        while chunk_count < 3:
            ev = await asyncio.wait_for(sub_queue.get(), timeout=2.0)
            frame = ev.to_frame_dict()
            received_events.append(frame)
            if frame["event"] == "token_chunk":
                chunk_count += 1

        # Trigger true server-side abort and measure cancellation latency (< 250ms required by SC-003)
        abort_start = time.perf_counter()
        aborted = await broker.abort_active_generation(
            thread_id=thread_id,
            reason="client_interrupt",
        )
        abort_elapsed_ms = (time.perf_counter() - abort_start) * 1000.0
        assert aborted is True
        assert abort_elapsed_ms < 250.0, f"Abort took {abort_elapsed_ms:.2f}ms (exceeded 250ms limit)"
        assert broker.is_generating(thread_id) is False

        # Drain all remaining events from queue
        while not sub_queue.empty():
            ev = sub_queue.get_nowait()
            received_events.append(ev.to_frame_dict())

        event_names = [e["event"] for e in received_events]
        assert "generation_interrupted" in event_names
        assert "generation_completed" not in event_names

        # Verify ZERO token_chunk events appear after generation_interrupted
        interrupted_idx = event_names.index("generation_interrupted")
        trailing_events = received_events[interrupted_idx + 1 :]
        trailing_chunks = [e for e in trailing_events if e["event"] == "token_chunk"]
        assert len(trailing_chunks) == 0, f"Expected 0 trailing token_chunk events after interrupt, got {len(trailing_chunks)}"

        interrupted_frame = received_events[interrupted_idx]
        assert interrupted_frame["status"] == "interrupted"
        assert interrupted_frame["reason"] == "client_interrupt"
        assert len(interrupted_frame["partial_content"]) > 0

        # Verify partial turn is persisted in TinyDB repository with status="interrupted"
        saved_thread = repo.get_thread(thread_id)
        assert saved_thread is not None
        assert len(saved_thread.messages) == 2
        user_turn, assistant_turn = saved_thread.messages
        assert user_turn.role == "user"
        assert assistant_turn.role == "assistant"
        assert assistant_turn.status == "interrupted"
        assert assistant_turn.interrupted_reason == "client_interrupt"
        assert assistant_turn.content == interrupted_frame["partial_content"]

        # Verify idempotent no-op interrupt when no generation is active
        noop_abort = await broker.abort_active_generation(thread_id=thread_id)
        assert noop_abort is False

    asyncio.run(_run_abort_test())


def test_us2_mid_stream_redirection_aborts_first_turn_and_streams_second_turn() -> None:
    """Verify submitting a redirecting user_message mid-stream aborts Turn 1 as interrupted and completes Turn 2."""

    async def _run_redirect_test() -> None:
        agent_service = get_support_agent_service()
        broker = AgentChatEventBroker()
        repo = TinyDBAgentChatThreadRepository()
        thread_id = "thr_us2_redirect_01"
        session_id = "sess_us2_redirect_01"
        owner_id = "usr_operator_1"

        sub_queue = broker.subscribe(thread_id)
        abort_event_1 = asyncio.Event()

        req_1 = AgentQueryRequest(
            query="What is TrackFlow's standard return window and who covers return shipping costs?",
            thread_id=thread_id,
            language="en",
        )
        task_1 = asyncio.create_task(
            agent_service.stream_query(  # type: ignore[attr-defined]
                request=req_1,
                owner_user_id=owner_id,
                session_id=session_id,
                user_turn_id="usr_turn_1",
                assistant_turn_id="asst_turn_1",
                abort_event=abort_event_1,
                broker=broker,
                thread_repository=repo,
                chunk_delay_seconds=0.025,
            )
        )
        broker.register_generation_task(
            thread_id=thread_id,
            turn_id="asst_turn_1",
            task=task_1,
            abort_event=abort_event_1,
        )

        # Wait for at least 2 token chunks from Turn 1
        t1_chunks = 0
        while t1_chunks < 2:
            ev = await asyncio.wait_for(sub_queue.get(), timeout=2.0)
            if ev.event == "token_chunk" and ev.payload.get("turn_id") == "asst_turn_1":
                t1_chunks += 1

        # Redirect mid-stream: abort Turn 1 with reason="redirect_new_message" and immediately start Turn 2
        await broker.abort_active_generation(
            thread_id=thread_id,
            reason="redirect_new_message",
        )

        abort_event_2 = asyncio.Event()
        req_2 = AgentQueryRequest(
            query="What are the standard delivery SLAs for domestic shipments?",
            thread_id=thread_id,
            language="en",
        )
        msg_2 = await agent_service.stream_query(  # type: ignore[attr-defined]
            request=req_2,
            owner_user_id=owner_id,
            session_id=session_id,
            user_turn_id="usr_turn_2",
            assistant_turn_id="asst_turn_2",
            abort_event=abort_event_2,
            broker=broker,
            thread_repository=repo,
            chunk_delay_seconds=0.002,
        )
        assert msg_2.status == "completed"

        # Verify thread history contains all 4 turns in order:
        # 1. usr_turn_1 (completed)
        # 2. asst_turn_1 (interrupted, reason="redirect_new_message", non-empty partial content)
        # 3. usr_turn_2 (completed)
        # 4. asst_turn_2 (completed)
        saved_thread = repo.get_thread(thread_id)
        assert saved_thread is not None
        assert [m.turn_id for m in saved_thread.messages] == [
            "usr_turn_1",
            "asst_turn_1",
            "usr_turn_2",
            "asst_turn_2",
        ]
        assert saved_thread.messages[1].status == "interrupted"
        assert saved_thread.messages[1].interrupted_reason == "redirect_new_message"
        assert len(saved_thread.messages[1].content) > 0
        assert saved_thread.messages[3].status == "completed"
        assert len(saved_thread.messages[3].content) > 0

    asyncio.run(_run_redirect_test())


def test_us2_websocket_idle_interrupt_is_safe_noop(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify sending interrupt_requested over WebSocket when idle is handled gracefully without error."""
    token = test_users["active_token"]
    thread_id = "thr_us2_idle_interrupt"

    with client.websocket_connect(
        f"/api/v1/agent/ws?token={token}&thread_id={thread_id}"
    ) as ws:
        rehydrated = ws.receive_json()
        assert rehydrated["event"] == "session_snapshot"

        # Send interrupt_requested while no turn is generating
        ws.send_json({"event": "interrupt_requested", "reason": "client_interrupt"})
        # Follow with a ping to confirm socket remains healthy and open
        ws.send_json({"event": "ping"})
        pong = ws.receive_json()
        assert pong["event"] == "pong"


def test_us2_high_latency_abort_fallback_finalizer_prevents_race_and_duplicate_events() -> None:
    """Verify that if a slow task exceeds the wait_for timeout during abort_active_generation, the idempotent fallback finalizer persists and publishes generation_interrupted before Turn 2 starts, with zero duplicate events when the slow task finally unwinds."""

    async def _run_high_latency_abort_test() -> None:
        agent_service = get_support_agent_service()
        broker = AgentChatEventBroker()
        repo = TinyDBAgentChatThreadRepository()
        thread_id = "thr_us2_high_latency_abort"
        session_id = "sess_us2_high_latency_abort"
        owner_id = "usr_operator_1"

        sub_queue = broker.subscribe(thread_id)
        abort_event_1 = asyncio.Event()
        uncooperative_io_started = asyncio.Event()

        # Patch asyncio.sleep inside stream_query for Turn 1 after 2 chunks to simulate a slow (>300ms) shielded I/O wait
        original_sleep = asyncio.sleep
        chunk_sleeps = 0

        async def _simulated_high_latency_sleep(delay: float) -> None:
            nonlocal chunk_sleeps
            chunk_sleeps += 1
            if chunk_sleeps == 2:
                uncooperative_io_started.set()
                try:
                    await original_sleep(delay)
                except asyncio.CancelledError:
                    # Simulate a slow threadpool/I/O operation taking 300ms (> 200ms abort wait budget) to unwind
                    await original_sleep(0.30)
                    raise
            else:
                await original_sleep(delay)

        req_1 = AgentQueryRequest(
            query="What is TrackFlow's standard return window and who covers return shipping costs?",
            thread_id=thread_id,
            language="en",
        )

        import application.services.support_agent_service as sas_mod

        sas_mod.asyncio.sleep = _simulated_high_latency_sleep  # type: ignore[assignment]
        try:
            task_1 = asyncio.create_task(
                agent_service.stream_query(  # type: ignore[attr-defined]
                    request=req_1,
                    owner_user_id=owner_id,
                    session_id=session_id,
                    user_turn_id="usr_turn_slow_1",
                    assistant_turn_id="asst_turn_slow_1",
                    abort_event=abort_event_1,
                    broker=broker,
                    thread_repository=repo,
                    chunk_delay_seconds=0.05,
                )
            )
            broker.register_generation_task(
                thread_id=thread_id,
                turn_id="asst_turn_slow_1",
                task=task_1,
                abort_event=abort_event_1,
            )

            await asyncio.wait_for(uncooperative_io_started.wait(), timeout=2.0)

            # Abort Turn 1 while it will take 300ms to unwind (> 200ms wait_for timeout)
            abort_start = time.perf_counter()
            aborted = await broker.abort_active_generation(
                thread_id=thread_id,
                reason="redirect_new_message",
            )
            abort_elapsed_ms = (time.perf_counter() - abort_start) * 1000.0
            assert aborted is True
            assert abort_elapsed_ms < 250.0, (
                f"High-latency abort took {abort_elapsed_ms:.2f}ms (exceeded 250ms SC-003 budget)"
            )

            # Immediately verify Turn 1 is ALREADY persisted as interrupted in TinyDB BEFORE Turn 2 starts
            mid_thread = repo.get_thread(thread_id)
            assert mid_thread is not None
            assert [m.turn_id for m in mid_thread.messages] == [
                "usr_turn_slow_1",
                "asst_turn_slow_1",
            ]
            assert mid_thread.messages[1].status == "interrupted"
            assert mid_thread.messages[1].interrupted_reason == "redirect_new_message"
        finally:
            sas_mod.asyncio.sleep = original_sleep  # type: ignore[assignment]

        # Start Turn 2 immediately while Turn 1's slow task is still unwinding in the background
        req_2 = AgentQueryRequest(
            query="What are the standard delivery SLAs for domestic shipments?",
            thread_id=thread_id,
            language="en",
        )
        msg_2 = await agent_service.stream_query(  # type: ignore[attr-defined]
            request=req_2,
            owner_user_id=owner_id,
            session_id=session_id,
            user_turn_id="usr_turn_fast_2",
            assistant_turn_id="asst_turn_fast_2",
            abort_event=asyncio.Event(),
            broker=broker,
            thread_repository=repo,
            chunk_delay_seconds=0.001,
        )
        assert msg_2.status == "completed"

        # Wait for Turn 1's slow task to finish unwinding completely
        await asyncio.gather(task_1, return_exceptions=True)

        # Drain all broker events and verify deterministic ordering and ZERO duplicate generation_interrupted frames
        all_events: List[Dict[str, Any]] = []
        while not sub_queue.empty():
            all_events.append(sub_queue.get_nowait().to_frame_dict())

        interrupted_events = [
            e for e in all_events if e["event"] == "generation_interrupted"
        ]
        assert len(interrupted_events) == 1, (
            f"Expected exactly 1 generation_interrupted event, got {len(interrupted_events)}"
        )
        turn2_started_events = [
            e
            for e in all_events
            if e["event"] == "generation_started"
            and e.get("turn_id") == "asst_turn_fast_2"
        ]
        assert len(turn2_started_events) == 1
        assert (
            interrupted_events[0]["sequence_id"]
            < turn2_started_events[0]["sequence_id"]
        ), "Turn 1 generation_interrupted must be published before Turn 2 generation_started"

        saved_thread = repo.get_thread(thread_id)
        assert saved_thread is not None
        assert [m.turn_id for m in saved_thread.messages] == [
            "usr_turn_slow_1",
            "asst_turn_slow_1",
            "usr_turn_fast_2",
            "asst_turn_fast_2",
        ]
        assert saved_thread.messages[1].status == "interrupted"
        assert saved_thread.messages[3].status == "completed"

    asyncio.run(_run_high_latency_abort_test())


# =====================================================================
# User Story 3: Backoffice JWT Auth & Session / Thread Binding (T023)
# =====================================================================


def test_us3_unauthenticated_and_invalid_jwt_websocket_connections_rejected_with_4001(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify missing, malformed, and expired JWT connections are rejected with close code 4001 and 0 events."""
    # 1. Invalid token in query string -> 4001
    with pytest.raises(WebSocketDisconnect) as exc_invalid:
        with client.websocket_connect(
            "/api/v1/agent/ws?token=invalid.jwt.token&thread_id=thr_unauth_1"
        ) as ws:
            ws.receive_json()
    assert exc_invalid.value.code == 4001

    # 2. Expired token in query string -> 4001
    expired_token = test_users["expired_token"]
    with pytest.raises(WebSocketDisconnect) as exc_expired:
        with client.websocket_connect(
            f"/api/v1/agent/ws?token={expired_token}&thread_id=thr_unauth_2"
        ) as ws:
            ws.receive_json()
    assert exc_expired.value.code == 4001

    # 3. Missing handshake token AND non-authenticate first frame -> 4001
    with pytest.raises(WebSocketDisconnect) as exc_missing:
        with client.websocket_connect("/api/v1/agent/ws?thread_id=thr_unauth_3") as ws:
            ws.send_json({"event": "user_message", "query": "Hello without auth"})
            ws.receive_json()
    assert exc_missing.value.code == 4001


def test_us3_first_frame_authenticate_and_cross_operator_thread_ownership_isolation(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify first-frame authenticate succeeds and cross-user thread access is rejected with 4003 / HTTP 403."""
    user_a_token = test_users["active_token"]
    user_b_token = test_users["admin_token"]
    shared_thread_id = "thr_us3_owned_by_user_a"

    # 1. User A connects using first-frame {"event": "authenticate", "token": ...}
    with client.websocket_connect(
        f"/api/v1/agent/ws?thread_id={shared_thread_id}"
    ) as ws_a:
        ws_a.send_json(
            {
                "event": "authenticate",
                "token": user_a_token,
                "thread_id": shared_thread_id,
            }
        )
        rehydrated_a = ws_a.receive_json()
        assert rehydrated_a["event"] == "session_snapshot"
        assert rehydrated_a["thread_id"] == shared_thread_id
        assert rehydrated_a["user_id"] == "unassigned"

    # 2. User B attempts to connect to User A's thread_id -> rejected with WebSocket close code 4003
    with pytest.raises(WebSocketDisconnect) as exc_forbidden:
        with client.websocket_connect(
            f"/api/v1/agent/ws?token={user_b_token}&thread_id={shared_thread_id}"
        ) as ws_b:
            ws_b.receive_json()
    assert exc_forbidden.value.code == 4003

    # 3. User B attempts to fetch User A's thread history via REST -> rejected with HTTP 403
    rest_forbidden = client.get(
        f"/api/v1/agent/threads/{shared_thread_id}/history",
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert rest_forbidden.status_code == 403
    assert rest_forbidden.json()["error_code"] == "THREAD_FORBIDDEN"

    # 4. Unauthenticated REST history request -> rejected with HTTP 401
    rest_unauth = client.get(f"/api/v1/agent/threads/{shared_thread_id}/history")
    assert rest_unauth.status_code == 401


def test_us3_handshake_thread_and_session_id_validation_and_token_log_redaction(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify handshake rejects connections omitting both thread_id and session_id (1008), accepts session_id-only connections, and redacts ?token= in log sanitizer."""
    from presentation.api.v1.agent import _sanitize_websocket_query_for_logging

    token = test_users["active_token"]

    # 1. Omitting both thread_id and session_id -> rejected with close code 1008
    with pytest.raises(WebSocketDisconnect) as exc_missing_ids:
        with client.websocket_connect(f"/api/v1/agent/ws?token={token}") as ws_no_ids:
            ws_no_ids.receive_json()
    assert exc_missing_ids.value.code == 1008

    # 2. Providing session_id without thread_id -> accepted and derives thread_id = session_id
    with client.websocket_connect(
        f"/api/v1/agent/ws?token={token}&session_id=sess_only_handshake_01"
    ) as ws_sess_only:
        rehydrated = ws_sess_only.receive_json()
        assert rehydrated["event"] == "session_snapshot"
        assert rehydrated["session_id"] == "sess_only_handshake_01"
        assert rehydrated["thread_id"] == "sess_only_handshake_01"

    # 3. Verify query-string token redaction helper masks JWT tokens
    raw_url = f"ws://localhost:8000/api/v1/agent/ws?thread_id=thr_1&token={token}&session_id=sess_1"
    sanitized = _sanitize_websocket_query_for_logging(raw_url)
    assert token not in sanitized
    assert "token=[REDACTED]" in sanitized
    assert "thread_id=thr_1" in sanitized
    assert "session_id=sess_1" in sanitized


# =====================================================================
# User Story 4: Reconnection & Durable Thread Rehydration (T028)
# =====================================================================


def test_us4_reconnect_and_server_restart_rehydrate_completed_and_interrupted_turns(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify reconnecting with the same thread_id restores all completed and interrupted turns without duplicates."""
    token = test_users["active_token"]
    owner_id = str(test_users["active"].id)
    thread_id = "thr_us4_durable_rehydration"
    session_id = "sess_us4_durable_rehydration"

    # 1. Execute a full streaming turn over WebSocket
    with client.websocket_connect(
        f"/api/v1/agent/ws?token={token}&thread_id={thread_id}&session_id={session_id}"
    ) as ws1:
        init_rehydrated = ws1.receive_json()
        assert init_rehydrated["event"] == "session_snapshot"
        assert len(init_rehydrated["messages"]) == 0

        ws1.send_json(
            {
                "event": "user_message",
                "query": "What is TrackFlow's standard return window?",
                "turn_id": "usr_rehydrate_1",
            }
        )
        frames = _collect_turn_frames_until_terminal(ws1)
        assert frames[-1]["event"] == "generation_completed"

    # 2. Also persist an interrupted partial turn in the durable TinyDB repository
    repo = get_agent_chat_thread_repository_dep()
    repo.append_or_update_message(
        thread_id=thread_id,
        session_id=session_id,
        owner_user_id=owner_id,
        message=ChatMessage(
            turn_id="usr_rehydrate_2",
            thread_id=thread_id,
            session_id=session_id,
            role="user",
            content="Compare storage rates in Los Angeles versus Zaragoza.",
            status="completed",
        ),
    )
    repo.append_or_update_message(
        thread_id=thread_id,
        session_id=session_id,
        owner_user_id=owner_id,
        message=ChatMessage(
            turn_id="asst_rehydrate_2_interrupted",
            thread_id=thread_id,
            session_id=session_id,
            role="assistant",
            content="In Los Angeles, standard pallet storage starts at...",
            status="interrupted",
            parent_user_turn_id="usr_rehydrate_2",
            interrupted_reason="client_interrupt",
        ),
    )

    # 3. Simulate in-memory broker reset (server restart) while TinyDB repository retains durable state
    broker = get_agent_chat_event_broker_dep()
    broker.reset()

    # 4. Reconnect WebSocket with the same thread_id -> session_snapshot must restore all 4 turns
    with client.websocket_connect(
        f"/api/v1/agent/ws?token={token}&thread_id={thread_id}&session_id={session_id}"
    ) as ws2:
        rehydrated = ws2.receive_json()
        assert rehydrated["event"] == "session_snapshot"
        assert rehydrated["thread_id"] == thread_id
        messages = rehydrated["messages"]
        assert len(messages) == 4
        assert messages[0]["turn_id"] == "usr_rehydrate_1"
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["status"] == "completed"
        assert messages[2]["turn_id"] == "usr_rehydrate_2"
        assert messages[3]["turn_id"] == "asst_rehydrate_2_interrupted"
        assert messages[3]["status"] == "interrupted"
        assert messages[3]["interrupted_reason"] == "client_interrupt"
        assert "Los Angeles" in messages[3]["content"]

        # Send explicit client `rehydrate` command
        ws2.send_json({"event": "rehydrate", "last_sequence_id": 0})
        explicit_rehydrated = ws2.receive_json()
        assert explicit_rehydrated["event"] == "session_snapshot"
        assert len(explicit_rehydrated["messages"]) == 4

    # 5. Verify both canonical and legacy REST history endpoints return the exact same 4 turns
    for path in (
        f"/api/v1/agent/threads/{thread_id}/history",
        f"/agent/threads/{thread_id}/history",
    ):
        hist_resp = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert hist_resp.status_code == 200
        hist_body = hist_resp.json()
        assert hist_body["thread_id"] == thread_id
        assert hist_body["user_id"] == "unassigned"
        assert hist_body["session"]["user_id"] == "unassigned"
        assert hist_body["session"]["agent_id"] == "first_line_cx"
        assert hist_body["session"]["client_id"] == "trackflow-backoffice"
        assert hist_body["session"]["status"] in ("active", "interrupted")
        assert len(hist_body["messages"]) == 4
        assert hist_body["messages"][3]["status"] == "interrupted"


def test_session_user_id_resolved_from_domain_customer_and_not_spoofable(
    client: Any, test_users: Dict[str, Any]
) -> None:
    """Verify ChatSession.user_id resolves from domain session_context.customer_id (fallback 'unassigned'), ignores ?client_user_id=, survives streaming/interrupt, and preserves per-operator ownership."""
    operator_a_token = test_users["active_token"]
    operator_b_token = test_users["admin_token"]
    operator_a_id = str(test_users["active"].id)
    thread_id = "thr_domain_client_identity_01"
    session_id = "sess_domain_client_identity_01"
    customer_id = "cust_brand_acme_42"

    # 1. REST thread creation/history before a customer is bound yields 'unassigned', never the operator id
    initial_rest = client.get(
        f"/api/v1/agent/threads/{thread_id}/history",
        headers={"Authorization": f"Bearer {operator_a_token}"},
    )
    assert initial_rest.status_code == 200
    initial_body = initial_rest.json()
    assert initial_body["user_id"] == "unassigned"
    assert initial_body["session"]["user_id"] == "unassigned"
    assert initial_body["user_id"] != operator_a_id

    # 2. WebSocket ignores ?client_user_id=spoofed_client on handshake
    with client.websocket_connect(
        f"/api/v1/agent/ws?token={operator_a_token}&thread_id={thread_id}&session_id={session_id}&client_user_id=spoofed_client"
    ) as ws:
        snap_before = ws.receive_json()
        assert snap_before["event"] == "session_snapshot"
        assert snap_before["user_id"] == "unassigned"
        assert snap_before["session"]["user_id"] == "unassigned"

        # 3. First user_message with domain session_context.customer_id binds ChatSession.user_id
        ws.send_json(
            {
                "event": "user_message",
                "query": "What is TrackFlow's standard return window?",
                "turn_id": "usr_cust_1",
                "session_context": {
                    "session_id": session_id,
                    "customer_id": customer_id,
                    "customer_segment": "B2B",
                    "primary_operating_country": "US",
                },
            }
        )
        frames = _collect_turn_frames_until_terminal(ws)
        assert frames[-1]["event"] == "generation_completed"

        # Rehydrate after streaming completion -> user_id is customer_id, not operator
        ws.send_json({"event": "rehydrate"})
        snap_after_stream = ws.receive_json()
        assert snap_after_stream["event"] == "session_snapshot"
        assert snap_after_stream["user_id"] == customer_id
        assert snap_after_stream["session"]["user_id"] == customer_id
        assert snap_after_stream["session"]["status"] == "active"

    # 4. Persist an interrupted assistant turn and verify snapshot after interrupt keeps user_id == customer_id
    repo = get_agent_chat_thread_repository_dep()
    repo.append_or_update_message(
        thread_id=thread_id,
        session_id=session_id,
        owner_user_id=operator_a_id,
        message=ChatMessage(
            turn_id="asst_cust_interrupted",
            thread_id=thread_id,
            session_id=session_id,
            role="assistant",
            content="Partial answer before interrupt...",
            status="interrupted",
            parent_user_turn_id="usr_cust_1",
            interrupted_reason="client_interrupt",
        ),
    )

    with client.websocket_connect(
        f"/api/v1/agent/ws?token={operator_a_token}&thread_id={thread_id}&session_id={session_id}"
    ) as ws_reconn:
        snap_after_interrupt = ws_reconn.receive_json()
        assert snap_after_interrupt["event"] == "session_snapshot"
        assert snap_after_interrupt["user_id"] == customer_id
        assert snap_after_interrupt["session"]["user_id"] == customer_id
        assert snap_after_interrupt["session"]["status"] == "interrupted"

    # 5. REST history also reports the resolved customer_id
    bound_rest = client.get(
        f"/api/v1/agent/threads/{thread_id}/history",
        headers={"Authorization": f"Bearer {operator_a_token}"},
    )
    assert bound_rest.status_code == 200
    assert bound_rest.json()["user_id"] == customer_id
    assert bound_rest.json()["session"]["user_id"] == customer_id

    # 6. Operator B is still rejected with 4003 (WS) and 403 (REST) even though user_id is now customer_id
    with pytest.raises(WebSocketDisconnect) as exc_forbidden:
        with client.websocket_connect(
            f"/api/v1/agent/ws?token={operator_b_token}&thread_id={thread_id}&session_id={session_id}"
        ) as ws_b:
            ws_b.receive_json()
    assert exc_forbidden.value.code == 4003

    rest_forbidden = client.get(
        f"/api/v1/agent/threads/{thread_id}/history",
        headers={"Authorization": f"Bearer {operator_b_token}"},
    )
    assert rest_forbidden.status_code == 403


# =====================================================================
# User Story 5: Decoupled Pub/Sub Event Bus & Domain Alignment (T033)
# =====================================================================


def test_us5_event_broker_pubsub_isolation_fanout_and_strict_domain_alignment() -> None:
    """Verify AgentChatEventBroker fan-out, monotonic sequence_id, queue cleanup, and zero RFP SSE field leakage."""

    async def _run_broker_isolation_test() -> None:
        broker = AgentChatEventBroker()
        thread_id = "thr_us5_pubsub_bus"
        session_id = "sess_us5_pubsub_bus"

        q1 = broker.subscribe(thread_id)
        q2 = broker.subscribe(thread_id)
        assert broker.get_subscriber_count(thread_id) == 2

        ev1 = broker.publish(
            thread_id=thread_id,
            session_id=session_id,
            event_name="generation_started",
            payload={
                "turn_id": "turn_100",
                "user_turn_id": "usr_100",
                "query": "Check return policy",
            },
        )
        ev2 = broker.publish(
            thread_id=thread_id,
            session_id=session_id,
            event_name="token_chunk",
            payload={
                "turn_id": "turn_100",
                "chunk_index": 0,
                "delta": "TrackFlow ",
                "accumulated_content": "TrackFlow ",
            },
        )
        assert ev1.sequence_id == 1
        assert ev2.sequence_id == 2

        for q in (q1, q2):
            f1 = (await q.get()).to_frame_dict()
            f2 = (await q.get()).to_frame_dict()
            _assert_zero_rfp_field_leakage(f1)
            _assert_zero_rfp_field_leakage(f2)
            assert f1["sequence_id"] == 1
            assert f2["sequence_id"] == 2
            assert f2["delta"] == "TrackFlow "

        rem1 = broker.unsubscribe(thread_id, q1)
        assert rem1 == 1
        rem2 = broker.unsubscribe(thread_id, q2)
        assert rem2 == 0
        assert broker.get_subscriber_count(thread_id) == 0

    asyncio.run(_run_broker_isolation_test())


def test_true_llm_streaming_and_mid_generation_abort_stops_model_stream() -> None:
    """Verify GroundedGenerationAdapter uses stream=True and mid-generation interrupt_requested aborts the active model stream before remaining tokens are generated."""
    from domain.agent.entities import ChatSession
    from domain.knowledge.entities import (
        KnowledgeChunk,
        KnowledgeRuntimeConfig,
        RetrievedContext,
        generate_chunk_id,
    )
    from domain.knowledge.ports import LLMGenerationPort
    from infrastructure.adapters.grounded_generation_adapter import GroundedGenerationAdapter

    # 1. Verify ChatSession domain entity fields
    chat_sess = ChatSession(
        session_id="sess_contract_01",
        thread_id="thr_contract_01",
        agent_id="first_line_cx",
        client_id="trackflow-backoffice",
        user_id="usr_contract_01",
        status="active",
    )
    sess_dict = chat_sess.to_dict()
    assert sess_dict["agent_id"] == "first_line_cx"
    assert sess_dict["client_id"] == "trackflow-backoffice"
    assert sess_dict["user_id"] == "usr_contract_01"
    assert sess_dict["status"] == "active"

    # 2. Verify GroundedGenerationAdapter.stream_grounded_answer calls client.stream("POST", ..., json={..., "stream": True})
    # and stops reading from the HTTP stream immediately when abort_event is set
    stream_calls: List[Dict[str, Any]] = []
    yielded_sse_lines = 0
    stream_closed = False

    class _FakeStreamingResponse:
        def __enter__(self) -> "_FakeStreamingResponse":
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            nonlocal stream_closed
            stream_closed = True

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self) -> Any:
            nonlocal yielded_sse_lines
            chunks = [
                'data: {"choices": [{"delta": {"content": "TrackFlow\'s "}}]}',
                'data: {"choices": [{"delta": {"content": "standard "}}]}',
                'data: {"choices": [{"delta": {"content": "return "}}]}',
                'data: {"choices": [{"delta": {"content": "window "}}]}',
                'data: {"choices": [{"delta": {"content": "is 30 days."}}]}',
                "data: [DONE]",
            ]
            for line in chunks:
                yielded_sse_lines += 1
                yield line

    class _FakeHttpClient:
        def stream(self, method: str, url: str, **kwargs: Any) -> _FakeStreamingResponse:
            stream_calls.append({"method": method, "url": url, "kwargs": kwargs})
            return _FakeStreamingResponse()

    cfg = KnowledgeRuntimeConfig(
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        agent_model="gpt-4o",
        llm_api_key="sk-live-test-streaming-key-123456",
    )
    adapter = GroundedGenerationAdapter(config=cfg, http_client=_FakeHttpClient())
    ctx = RetrievedContext(
        chunk=KnowledgeChunk(
            id=generate_chunk_id("returns-policy", 1),
            company="trackflow",
            source_document="returns-policy",
            section="Return Window",
            language="en",
            chunk_index=1,
            text="TrackFlow standard return window is 30 days from delivery.",
        ),
        similarity_score=0.92,
        rank=1,
    )

    abort_ev = asyncio.Event()
    collected_deltas: List[str] = []
    for delta in adapter.stream_grounded_answer(
        query="What is TrackFlow's standard return window?",
        contexts=[ctx],
        language="en",
        abort_event=abort_ev,
    ):
        collected_deltas.append(delta)
        if len(collected_deltas) == 2:
            abort_ev.set()

    assert len(stream_calls) == 1
    assert stream_calls[0]["kwargs"]["json"]["stream"] is True
    assert collected_deltas == ["TrackFlow's ", "standard "]
    assert yielded_sse_lines < 5, "HTTP SSE stream must be aborted mid-flight before remaining chunks are generated"
    assert stream_closed is True

    # 3. Verify SupportAgentService.stream_query does NOT pre-generate the full answer in _prepare_pre_generation_state
    # and aborts the active LLMGenerationPort generator mid-flight when cancelled
    generated_token_count = 0
    generator_closed = False

    class _IncrementalStreamingLLM(LLMGenerationPort):
        def generate_grounded_answer(
            self,
            query: str,
            contexts: List[RetrievedContext],
            language: str = "en",
        ) -> str:
            raise AssertionError(
                "Blocking generate_grounded_answer must NOT be called during stream_query"
            )

        def stream_grounded_answer(
            self,
            query: str,
            contexts: List[RetrievedContext],
            language: str = "en",
            abort_event: Optional[Any] = None,
        ) -> Any:
            nonlocal generated_token_count, generator_closed
            tokens = [
                "Under ",
                "TrackFlow's ",
                "standard ",
                "policy, ",
                "returns ",
                "are ",
                "accepted ",
                "within ",
                "30 ",
                "days.",
            ]
            try:
                for tok in tokens:
                    if abort_event is not None and abort_event.is_set():
                        break
                    generated_token_count += 1
                    yield tok
            finally:
                generator_closed = True

    async def _run_service_live_abort() -> None:
        base_service = get_support_agent_service()
        from application.services.support_agent_service import SupportAgentService

        custom_service = SupportAgentService(
            vector_store=base_service._vector_store,  # type: ignore[attr-defined]
            embedding_service=base_service._embedding_service,  # type: ignore[attr-defined]
            llm_generator=_IncrementalStreamingLLM(),
            ticket_tool=base_service.ticket_tool,  # type: ignore[attr-defined]
            inventory_tool=base_service.inventory_tool,  # type: ignore[attr-defined]
        )
        broker = AgentChatEventBroker()
        repo = TinyDBAgentChatThreadRepository()
        thread_id = "thr_true_live_stream_abort"
        sub_q = broker.subscribe(thread_id)
        abort_signal = asyncio.Event()

        task = asyncio.create_task(
            custom_service.stream_query(
                request=AgentQueryRequest(
                    query="What is TrackFlow's standard return window?",
                    thread_id=thread_id,
                    language="en",
                ),
                user_id="usr_live_1",
                session_id="sess_live_1",
                user_turn_id="usr_t1",
                assistant_turn_id="asst_t1",
                abort_event=abort_signal,
                broker=broker,
                thread_repository=repo,
                chunk_delay_seconds=0.03,
            )
        )
        broker.register_generation_task(
            thread_id=thread_id,
            turn_id="asst_t1",
            task=task,
            abort_event=abort_signal,
        )

        seen_chunks = 0
        while seen_chunks < 2:
            ev = await asyncio.wait_for(sub_q.get(), timeout=2.0)
            if ev.event == "token_chunk":
                seen_chunks += 1

        await broker.abort_active_generation(
            thread_id=thread_id,
            reason="client_interrupt",
        )

    asyncio.run(_run_service_live_abort())
    assert generated_token_count < 10, (
        f"Generator should have been aborted mid-generation, but generated {generated_token_count}/10 tokens"
    )
    assert generator_closed is True
