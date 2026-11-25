"""Async-safe and thread-safe pub/sub event broker for Support Agent WebSocket streaming chat (T006).

Implements `AgentChatEventBrokerPort` in `services/api/infrastructure/messaging/`:
- Decouples the Support Agent streaming producer from the WebSocket transport layer (FR-004)
- Manages per-thread subscriber queues (`asyncio.Queue[AgentChatStreamEvent]`) and monotonic
  per-thread `sequence_id` counters
- Tracks active generation `asyncio.Task` handles and cooperative `abort_event` signals
- Performs true server-side cooperative task cancellation (`abort_active_generation`) within
  `< 250ms` when an `interrupt`, redirecting `user_message`, or last-subscriber disconnect
  occurs (FR-008, SC-003).
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import threading
from typing import Any, Callable, Dict, Optional, Tuple

from domain.agent.entities import (
    AgentChatEventName,
    AgentChatStreamEvent,
    ChatInterruptedReason,
)
from domain.agent.ports import AgentChatEventBrokerPort

logger = logging.getLogger("agent_chat_event_broker")


@dataclass
class _ActiveGenerationHandle:
    """Internal handle tracking a running generation task and its cooperative cancellation signal."""

    thread_id: str
    turn_id: str
    task: asyncio.Task[Any]
    abort_event: asyncio.Event
    abort_reason: ChatInterruptedReason = "client_interrupt"
    on_abort_finalize: Optional[Callable[[ChatInterruptedReason], Any]] = None
    finalized: bool = False


class AgentChatEventBroker(AgentChatEventBrokerPort):
    """In-memory pub/sub broker and cooperative task cancellation manager for Support Agent chat threads."""

    def __init__(self, max_queue_size: int = 512) -> None:
        """Initialize the broker with thread-safe channel structures."""
        self._max_queue_size = max_queue_size
        self._lock = threading.RLock()
        self._sequence_counters: Dict[str, int] = {}
        self._subscribers: Dict[
            str,
            Dict[
                int,
                Tuple[
                    asyncio.Queue[AgentChatStreamEvent],
                    Optional[asyncio.AbstractEventLoop],
                ],
            ],
        ] = {}
        self._active_tasks: Dict[str, _ActiveGenerationHandle] = {}
        self._abort_finalizers: Dict[
            Tuple[str, str], Callable[[ChatInterruptedReason], Any]
        ] = {}

    def subscribe(self, thread_id: str) -> asyncio.Queue[AgentChatStreamEvent]:
        """Register a new subscriber queue for `thread_id` and return it."""
        cleaned_thread = (thread_id or "").strip() or "default"
        queue: asyncio.Queue[AgentChatStreamEvent] = asyncio.Queue(
            maxsize=self._max_queue_size
        )
        try:
            loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        with self._lock:
            channel = self._subscribers.setdefault(cleaned_thread, {})
            channel[id(queue)] = (queue, loop)
            self._sequence_counters.setdefault(cleaned_thread, 0)
        return queue

    def unsubscribe(
        self, thread_id: str, queue: asyncio.Queue[AgentChatStreamEvent]
    ) -> int:
        """Remove a subscriber queue from `thread_id` and return remaining subscriber count."""
        cleaned_thread = (thread_id or "").strip() or "default"
        with self._lock:
            channel = self._subscribers.get(cleaned_thread)
            if channel is not None:
                channel.pop(id(queue), None)
                remaining = len(channel)
                if remaining == 0:
                    self._subscribers.pop(cleaned_thread, None)
                return remaining
            return 0

    def get_subscriber_count(self, thread_id: str) -> int:
        """Return the number of active WebSocket subscriber queues on `thread_id`."""
        cleaned_thread = (thread_id or "").strip() or "default"
        with self._lock:
            channel = self._subscribers.get(cleaned_thread)
            return len(channel) if channel is not None else 0

    def get_latest_sequence_id(self, thread_id: str) -> int:
        """Return the latest monotonic event sequence ID emitted for `thread_id`."""
        cleaned_thread = (thread_id or "").strip() or "default"
        with self._lock:
            return int(self._sequence_counters.get(cleaned_thread, 0))

    def sync_sequence_id(self, thread_id: str, sequence_id: int) -> None:
        """Ensure the broker's sequence counter for `thread_id` is at least `sequence_id`."""
        cleaned_thread = (thread_id or "").strip() or "default"
        with self._lock:
            current = self._sequence_counters.get(cleaned_thread, 0)
            if int(sequence_id) > current:
                self._sequence_counters[cleaned_thread] = int(sequence_id)

    def publish(
        self,
        thread_id: str,
        session_id: str,
        event_name: AgentChatEventName,
        payload: Dict[str, Any],
    ) -> AgentChatStreamEvent:
        """Assign the next monotonic sequence_id for `thread_id`, build an AgentChatStreamEvent, and fan out to all thread subscribers."""
        cleaned_thread = (thread_id or "").strip() or "default"
        cleaned_session = (session_id or "").strip() or cleaned_thread
        with self._lock:
            next_seq = self._sequence_counters.get(cleaned_thread, 0) + 1
            self._sequence_counters[cleaned_thread] = next_seq
            event = AgentChatStreamEvent(
                event=event_name,
                thread_id=cleaned_thread,
                session_id=cleaned_session,
                sequence_id=next_seq,
                payload=dict(payload),
                timestamp=datetime.now(timezone.utc),
            )
            channel = self._subscribers.get(cleaned_thread)
            subscribers_snapshot = list(channel.values()) if channel else []

        for queue, subscriber_loop in subscribers_snapshot:
            self._deliver_to_queue(queue, subscriber_loop, event)

        return event

    def _deliver_to_queue(
        self,
        queue: asyncio.Queue[AgentChatStreamEvent],
        subscriber_loop: Optional[asyncio.AbstractEventLoop],
        event: AgentChatStreamEvent,
    ) -> None:
        """Safely enqueue an AgentChatStreamEvent across same-loop or cross-thread callers."""
        try:
            current_loop: Optional[asyncio.AbstractEventLoop] = (
                asyncio.get_running_loop()
            )
        except RuntimeError:
            current_loop = None

        def _put_nonblocking() -> None:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        if (
            subscriber_loop is not None
            and not subscriber_loop.is_closed()
            and subscriber_loop is not current_loop
        ):
            try:
                subscriber_loop.call_soon_threadsafe(_put_nonblocking)
                return
            except RuntimeError:
                pass

        _put_nonblocking()

    def register_generation_task(
        self,
        thread_id: str,
        turn_id: str,
        task: asyncio.Task[Any],
        abort_event: asyncio.Event,
        on_abort_finalize: Optional[Callable[[ChatInterruptedReason], Any]] = None,
    ) -> None:
        """Register an active generation asyncio.Task and cooperative abort_event for `thread_id`."""
        cleaned_thread = (thread_id or "").strip() or "default"
        with self._lock:
            existing_finalizer = (
                on_abort_finalize
                or self._abort_finalizers.get((cleaned_thread, turn_id))
            )
            if existing_finalizer is not None:
                self._abort_finalizers[(cleaned_thread, turn_id)] = existing_finalizer
            handle = _ActiveGenerationHandle(
                thread_id=cleaned_thread,
                turn_id=turn_id,
                task=task,
                abort_event=abort_event,
                on_abort_finalize=existing_finalizer,
            )
            self._active_tasks[cleaned_thread] = handle

        def _cleanup_on_done(_DoneTask: asyncio.Future[Any]) -> None:
            with self._lock:
                self._abort_finalizers.pop((cleaned_thread, turn_id), None)
                current = self._active_tasks.get(cleaned_thread)
                if current is not None and current.turn_id == turn_id:
                    self._active_tasks.pop(cleaned_thread, None)

        task.add_done_callback(_cleanup_on_done)

    def register_abort_finalizer(
        self,
        thread_id: str,
        turn_id: str,
        finalizer: Callable[[ChatInterruptedReason], Any],
    ) -> None:
        """Register an idempotent synchronous finalizer callback for `(thread_id, turn_id)`.

        Guarantees that if a cancelled task exceeds the `< 250ms` wait budget during
        `abort_active_generation`, the broker still persists `status="interrupted"` and
        emits `generation_interrupted` deterministically before any redirected turn begins.
        """
        cleaned_thread = (thread_id or "").strip() or "default"
        with self._lock:
            self._abort_finalizers[(cleaned_thread, turn_id)] = finalizer
            handle = self._active_tasks.get(cleaned_thread)
            if handle is not None and handle.turn_id == turn_id:
                handle.on_abort_finalize = finalizer

    def get_abort_reason(self, thread_id: str) -> ChatInterruptedReason:
        """Return the recorded abort reason for the active generation on `thread_id`."""
        cleaned_thread = (thread_id or "").strip() or "default"
        with self._lock:
            handle = self._active_tasks.get(cleaned_thread)
            return handle.abort_reason if handle is not None else "client_interrupt"

    def is_generating(self, thread_id: str) -> bool:
        """Return True if a generation task is currently running on `thread_id`."""
        cleaned_thread = (thread_id or "").strip() or "default"
        with self._lock:
            handle = self._active_tasks.get(cleaned_thread)
            return (
                handle is not None
                and not handle.finalized
                and not handle.task.done()
            )

    async def abort_active_generation(
        self,
        thread_id: str,
        reason: ChatInterruptedReason = "client_interrupt",
        turn_id: Optional[str] = None,
    ) -> bool:
        """Signal cooperative abort and cancel any active generation task on `thread_id`.

        Awaits task finalization up to 200ms (`< 250ms` SC-003 budget) and invokes any
        registered idempotent abort finalizer if the underlying task is still unwinding
        from slow I/O, guaranteeing `generation_interrupted` and partial persistence
        complete deterministically before any new redirected turn starts (FR-008, FR-010, SC-003).
        """
        cleaned_thread = (thread_id or "").strip() or "default"
        with self._lock:
            handle = self._active_tasks.get(cleaned_thread)
            if handle is None or handle.finalized or handle.task.done():
                return False
            if turn_id is not None and turn_id.strip() and handle.turn_id != turn_id.strip():
                return False
            handle.abort_reason = reason
            handle.abort_event.set()
            task = handle.task
            active_turn_id = handle.turn_id

        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=0.20)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass

        finalizer: Optional[Callable[[ChatInterruptedReason], Any]] = None
        with self._lock:
            current = self._active_tasks.get(cleaned_thread)
            if current is not None and current.turn_id == active_turn_id:
                current.finalized = True
                finalizer = (
                    current.on_abort_finalize
                    or self._abort_finalizers.pop(
                        (cleaned_thread, active_turn_id), None
                    )
                )
                self._active_tasks.pop(cleaned_thread, None)
            else:
                finalizer = self._abort_finalizers.pop(
                    (cleaned_thread, active_turn_id), None
                )

        if finalizer is not None:
            try:
                finalizer(reason)
            except Exception:
                logger.debug(
                    "Fallback abort finalizer raised for thread_id=%s turn_id=%s",
                    cleaned_thread,
                    active_turn_id,
                )

        return True

    def reset(self) -> None:
        """Cancel any active tasks and clear all thread channels and sequence counters (for test isolation)."""
        with self._lock:
            handles = list(self._active_tasks.values())
            self._active_tasks.clear()
            self._abort_finalizers.clear()
            self._subscribers.clear()
            self._sequence_counters.clear()

        for h in handles:
            h.abort_event.set()
            if not h.task.done():
                try:
                    h.task.cancel()
                except Exception:
                    pass


_broker_singleton: Optional[AgentChatEventBroker] = None
_broker_singleton_lock = threading.Lock()


def get_agent_chat_event_broker_singleton() -> AgentChatEventBroker:
    """Return the process-wide singleton `AgentChatEventBroker` instance."""
    global _broker_singleton
    if _broker_singleton is None:
        with _broker_singleton_lock:
            if _broker_singleton is None:
                _broker_singleton = AgentChatEventBroker()
    return _broker_singleton


__all__ = ["AgentChatEventBroker", "get_agent_chat_event_broker_singleton"]
