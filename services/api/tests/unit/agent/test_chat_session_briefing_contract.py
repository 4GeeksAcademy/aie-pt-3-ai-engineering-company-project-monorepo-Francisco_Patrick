"""Contract tests pinning ChatSession to the briefing: status, agent_id and user_id."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from domain.agent.entities import (
    AuthenticatedSessionContext,
    ChatMessage,
    ChatSession,
    ChatThreadState,
    ChatTurnStatus,
    UNASSIGNED_CLIENT_USER_ID,
    normalize_chat_session_status,
)
from domain.agent.exceptions import ThreadOwnershipMismatchError
from infrastructure.adapters.tinydb_chat_thread_repository import (
    TinyDBAgentChatThreadRepository,
)

BRIEFING_STATUSES = {"active", "interrupted", "closed"}


def _assistant(status: ChatTurnStatus) -> ChatMessage:
    return ChatMessage(
        turn_id="turn_a",
        thread_id="t1",
        session_id="s1",
        role="assistant",
        content="partial",
        status=status,
    )


@pytest.mark.parametrize("turn_status", ["streaming", "interrupted", "error", "completed"])
def test_session_status_always_in_briefing_enum(turn_status: ChatTurnStatus) -> None:
    thread = ChatThreadState(
        thread_id="t1", session_id="s1", user_id="operator", messages=[_assistant(turn_status)]
    )
    assert thread.session.status in BRIEFING_STATUSES
    assert thread.to_dict()["status"] in BRIEFING_STATUSES
    assert thread.session.to_dict()["status"] in BRIEFING_STATUSES


def test_streaming_turn_keeps_session_active() -> None:
    thread = ChatThreadState(
        thread_id="t1", session_id="s1", user_id="operator", messages=[_assistant("streaming")]
    )
    assert thread.session.status == "active"


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [("streaming", "active"), ("disconnected", "interrupted"), ("bogus", "active"), ("closed", "closed")],
)
def test_legacy_status_values_are_normalized_on_read(legacy: str, expected: str) -> None:
    assert normalize_chat_session_status(legacy) == expected
    assert ChatSession.from_dict({"session_id": "s", "status": legacy}).status == expected
    state = ChatThreadState.from_dict({"thread_id": "t", "user_id": "op", "status": legacy})
    assert state.status == expected


def test_default_and_legacy_agent_id_is_first_line_cx() -> None:
    assert ChatSession(session_id="s", thread_id="t", user_id="u").agent_id == "first_line_cx"
    assert ChatSession.from_dict({"session_id": "s"}).agent_id == "first_line_cx"
    legacy = ChatSession.from_dict({"session_id": "s", "agent_id": "trackflow-support-agent"})
    assert legacy.agent_id == "first_line_cx"
    assert ChatThreadState(thread_id="t", session_id="s").session.agent_id == "first_line_cx"


def test_session_user_id_is_chatting_client_not_operator() -> None:
    session_ctx = AuthenticatedSessionContext(
        session_id="s",
        customer_id="client_9",
    )
    thread = ChatThreadState(
        thread_id="t",
        session_id="s",
        owner_user_id="operator_1",
        session_context=session_ctx,
    )
    payload: Dict[str, Any] = thread.to_dict()
    assert thread.user_id == "client_9"
    assert thread.owner_user_id == "operator_1"
    assert thread.session.user_id == "client_9"
    assert payload["user_id"] == "client_9"
    assert payload["session"]["user_id"] == "client_9"
    assert payload["owner_user_id"] == "operator_1"
    restored = ChatThreadState.from_dict(payload)
    assert restored.owner_user_id == "operator_1"
    assert restored.user_id == "client_9"
    assert restored.session.user_id == "client_9"


def test_session_user_id_falls_back_to_unassigned_without_client_context() -> None:
    thread = ChatThreadState(thread_id="t", session_id="s", owner_user_id="operator_1")
    assert thread.owner_user_id == "operator_1"
    assert thread.user_id == UNASSIGNED_CLIENT_USER_ID
    assert thread.session.user_id == UNASSIGNED_CLIENT_USER_ID
    restored = ChatThreadState.from_dict(thread.to_dict())
    assert restored.owner_user_id == "operator_1"
    assert restored.user_id == UNASSIGNED_CLIENT_USER_ID
    assert restored.session.user_id == UNASSIGNED_CLIENT_USER_ID


def test_legacy_persisted_thread_with_operator_in_user_id_remains_owned_by_operator() -> None:
    legacy_doc: Dict[str, Any] = {
        "thread_id": "t_legacy",
        "session_id": "s_legacy",
        "user_id": "operator_legacy_1",
        "status": "active",
        "messages": [],
    }
    restored = ChatThreadState.from_dict(legacy_doc)
    assert restored.owner_user_id == "operator_legacy_1"
    assert restored.user_id == UNASSIGNED_CLIENT_USER_ID
    assert restored.session.user_id == UNASSIGNED_CLIENT_USER_ID

    repo = TinyDBAgentChatThreadRepository()
    repo._table.insert(legacy_doc)  # simulate pre-existing legacy document on disk
    loaded = repo.get_thread("t_legacy")
    assert loaded is not None
    assert loaded.owner_user_id == "operator_legacy_1"
    assert loaded.session.user_id == UNASSIGNED_CLIENT_USER_ID
    assert [t.thread_id for t in repo.list_threads_by_owner(owner_user_id="operator_legacy_1")] == [
        "t_legacy"
    ]
    with pytest.raises(ThreadOwnershipMismatchError):
        repo.save_thread(
            ChatThreadState(
                thread_id="t_legacy",
                session_id="s_legacy",
                owner_user_id="operator_other_2",
            )
        )


def test_session_user_id_locks_to_first_customer_id_and_ignores_later_mismatch() -> None:
    repo = TinyDBAgentChatThreadRepository()
    initial = repo.save_thread(
        ChatThreadState(
            thread_id="t_lock",
            session_id="s_lock",
            owner_user_id="operator_1",
        )
    )
    assert initial.session.user_id == UNASSIGNED_CLIENT_USER_ID

    bound = repo.save_thread(
        ChatThreadState(
            thread_id="t_lock",
            session_id="s_lock",
            owner_user_id="operator_1",
            session_context=AuthenticatedSessionContext(
                session_id="s_lock",
                customer_id="cust_first_01",
            ),
        )
    )
    assert bound.session.user_id == "cust_first_01"

    mismatched = repo.save_thread(
        ChatThreadState(
            thread_id="t_lock",
            session_id="s_lock",
            owner_user_id="operator_1",
            session_context=AuthenticatedSessionContext(
                session_id="s_lock",
                customer_id="cust_other_99",
            ),
        )
    )
    assert mismatched.session.user_id == "cust_first_01"



