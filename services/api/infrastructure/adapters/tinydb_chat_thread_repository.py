"""Thread-safe TinyDB persistence adapter for TrackFlow Support Agent chat threads (T005).

Implements `AgentChatThreadRepositoryPort` in `services/api/infrastructure/adapters/`,
persisting multi-turn conversation timelines (`user`, `completed`, and `interrupted`
partial assistant turns), per-operator ownership (`owner_user_id`), and checkpoint
references so thread rehydration survives both transient WebSocket drops and server
restarts (FR-003, FR-009, FR-012, Clarification 4).
"""

from datetime import datetime, timezone
import os
import threading
from typing import List, Optional

from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from domain.agent.entities import (
    ChatMessage,
    ChatSessionStatus,
    ChatThreadState,
    MemoryProposal,
)
from domain.agent.exceptions import ThreadOwnershipMismatchError
from domain.agent.ports import AgentChatThreadRepositoryPort


class TinyDBAgentChatThreadRepository(AgentChatThreadRepositoryPort):
    """Thread-safe TinyDB adapter for storing and rehydrating Support Agent conversation threads."""

    def __init__(
        self,
        db: Optional[TinyDB] = None,
        db_path: Optional[str] = None,
        table_name: str = "agent_chat_threads",
    ) -> None:
        """Initialize the TinyDB chat thread repository.

        Args:
            db: Optional existing TinyDB instance (e.g. `TinyDB(storage=MemoryStorage)` for tests).
            db_path: Optional explicit file path for dedicated JSON storage.
            table_name: Document table name (defaults to `'agent_chat_threads'`).
        """
        self._lock = threading.RLock()
        if db is not None:
            self._db = db
        elif db_path is not None:
            resolved = os.path.abspath(db_path)
            dirname = os.path.dirname(resolved)
            if dirname and not os.path.exists(dirname):
                os.makedirs(dirname, exist_ok=True)
            self._db = TinyDB(resolved)
        else:
            env_path = os.environ.get("AGENT_CHAT_DB_PATH")
            if env_path:
                resolved = os.path.abspath(env_path)
                dirname = os.path.dirname(resolved)
                if dirname and not os.path.exists(dirname):
                    os.makedirs(dirname, exist_ok=True)
                self._db = TinyDB(resolved)
            else:
                self._db = TinyDB(storage=MemoryStorage)

        self._table = self._db.table(table_name)
        self._query = Query()

    def get_thread(self, thread_id: str) -> Optional[ChatThreadState]:
        """Retrieve a persisted ChatThreadState by its thread_id, or None if not found."""
        cleaned_id = (thread_id or "").strip()
        if not cleaned_id:
            return None
        with self._lock:
            docs = self._table.search(self._query.thread_id == cleaned_id)
            if not docs:
                return None
            return ChatThreadState.from_dict(dict(docs[0]))

    def save_thread(self, thread_state: ChatThreadState) -> ChatThreadState:
        """Insert or update a ChatThreadState record atomically.

        Enforces immutable thread ownership (`user_id`) once bound.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            existing_docs = self._table.search(
                self._query.thread_id == thread_state.thread_id
            )
            if existing_docs:
                existing = ChatThreadState.from_dict(dict(existing_docs[0]))
                if (
                    existing.user_id
                    and thread_state.user_id
                    and existing.user_id != thread_state.user_id
                ):
                    raise ThreadOwnershipMismatchError(
                        thread_id=thread_state.thread_id,
                        requester_user_id=thread_state.user_id,
                    )
                updated = ChatThreadState(
                    thread_id=thread_state.thread_id,
                    session_id=thread_state.session_id or existing.session_id,
                    user_id=existing.user_id or thread_state.user_id,
                    owner_email=thread_state.owner_email or existing.owner_email,
                    agent_id=thread_state.agent_id or existing.agent_id,
                    client_id=thread_state.client_id or existing.client_id,
                    status=thread_state.status or existing.status,
                    messages=list(thread_state.messages),
                    pending_proposal=thread_state.pending_proposal,
                    session_context=(
                        thread_state.session_context or existing.session_context
                    ),
                    latest_checkpoint_id=(
                        thread_state.latest_checkpoint_id
                        if thread_state.latest_checkpoint_id is not None
                        else existing.latest_checkpoint_id
                    ),
                    latest_sequence_id=max(
                        int(thread_state.latest_sequence_id),
                        int(existing.latest_sequence_id),
                    ),
                    created_at=existing.created_at,
                    updated_at=now,
                )
                self._table.update(
                    updated.to_dict(),
                    self._query.thread_id == thread_state.thread_id,
                )
                return updated

            created = ChatThreadState(
                thread_id=thread_state.thread_id,
                session_id=thread_state.session_id or thread_state.thread_id,
                user_id=thread_state.user_id,
                owner_email=thread_state.owner_email,
                agent_id=thread_state.agent_id,
                client_id=thread_state.client_id,
                status=thread_state.status,
                messages=list(thread_state.messages),
                pending_proposal=thread_state.pending_proposal,
                session_context=thread_state.session_context,
                latest_checkpoint_id=thread_state.latest_checkpoint_id,
                latest_sequence_id=int(thread_state.latest_sequence_id),
                created_at=thread_state.created_at or now,
                updated_at=now,
            )
            self._table.insert(created.to_dict())
            return created

    def append_or_update_message(
        self,
        thread_id: str,
        session_id: str,
        message: ChatMessage,
        user_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        owner_email: Optional[str] = None,
        pending_proposal: Optional[MemoryProposal] = None,
        latest_checkpoint_id: Optional[str] = None,
        latest_sequence_id: Optional[int] = None,
        agent_id: str = "trackflow-support-agent",
        client_id: str = "trackflow-backoffice",
        session_status: Optional[ChatSessionStatus] = None,
    ) -> ChatThreadState:
        """Append a new ChatMessage or update an existing turn (by turn_id) on a thread."""
        resolved_user_id = str(user_id or owner_user_id or "").strip()
        derived_status: ChatSessionStatus = (
            session_status
            if session_status is not None
            else (
                "streaming"
                if message.role == "assistant" and message.status == "streaming"
                else (
                    "interrupted"
                    if message.role == "assistant" and message.status == "interrupted"
                    else "active"
                )
            )
        )
        with self._lock:
            now = datetime.now(timezone.utc)
            existing = self.get_thread(thread_id)
            if existing is not None:
                if (
                    existing.user_id
                    and resolved_user_id
                    and existing.user_id != resolved_user_id
                ):
                    raise ThreadOwnershipMismatchError(
                        thread_id=thread_id,
                        requester_user_id=resolved_user_id,
                    )
                messages: List[ChatMessage] = []
                replaced = False
                for m in existing.messages:
                    if m.turn_id == message.turn_id:
                        messages.append(message)
                        replaced = True
                    else:
                        messages.append(m)
                if not replaced:
                    messages.append(message)

                resolved_proposal = (
                    pending_proposal
                    if pending_proposal is not None
                    else (
                        message.memory_proposal
                        if message.memory_proposal is not None
                        else existing.pending_proposal
                    )
                )
                resolved_seq = (
                    max(int(latest_sequence_id), existing.latest_sequence_id)
                    if latest_sequence_id is not None
                    else existing.latest_sequence_id
                )
                updated_state = ChatThreadState(
                    thread_id=thread_id,
                    session_id=session_id or existing.session_id or thread_id,
                    user_id=existing.user_id,
                    owner_email=owner_email or existing.owner_email,
                    agent_id=agent_id or existing.agent_id,
                    client_id=client_id or existing.client_id,
                    status=derived_status,
                    messages=messages,
                    pending_proposal=resolved_proposal,
                    session_context=existing.session_context,
                    latest_checkpoint_id=(
                        latest_checkpoint_id
                        if latest_checkpoint_id is not None
                        else existing.latest_checkpoint_id
                    ),
                    latest_sequence_id=resolved_seq,
                    created_at=existing.created_at,
                    updated_at=now,
                )
                return self.save_thread(updated_state)

            new_state = ChatThreadState(
                thread_id=thread_id,
                session_id=session_id or thread_id,
                user_id=resolved_user_id,
                owner_email=owner_email,
                agent_id=agent_id,
                client_id=client_id,
                status=derived_status,
                messages=[message],
                pending_proposal=pending_proposal or message.memory_proposal,
                session_context=None,
                latest_checkpoint_id=latest_checkpoint_id,
                latest_sequence_id=int(latest_sequence_id or 0),
                created_at=now,
                updated_at=now,
            )
            return self.save_thread(new_state)

    def list_threads_by_owner(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        owner_user_id: Optional[str] = None,
    ) -> List[ChatThreadState]:
        """List conversation threads owned by a specific authenticated user ordered newest first."""
        cleaned_owner = str(user_id or owner_user_id or "").strip()
        if not cleaned_owner:
            return []
        with self._lock:
            docs = self._table.search(
                (self._query.user_id == cleaned_owner)
                | (self._query.owner_user_id == cleaned_owner)
            )
            threads = [ChatThreadState.from_dict(dict(d)) for d in docs]
            threads.sort(key=lambda t: t.updated_at, reverse=True)
            return threads[: max(1, int(limit))]

    def clear(self) -> None:
        """Clear all stored conversation thread records (for deterministic test isolation)."""
        with self._lock:
            self._table.truncate()


__all__ = ["TinyDBAgentChatThreadRepository"]
