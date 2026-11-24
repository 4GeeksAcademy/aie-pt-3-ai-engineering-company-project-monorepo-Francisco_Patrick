"""Thread-safe and async-safe in-memory SSE broadcaster for real-time RFP ticket notifications."""

import asyncio
from collections import deque
from datetime import datetime, timezone
import logging
import threading
from typing import Deque, Dict, List, Optional, Tuple

from domain.rfp.entities import RFPTicketCreatedEvent, SSEEnvelope
from domain.rfp.ports import RFPNotificationBroadcasterPort

logger = logging.getLogger("rfp_notification_broadcaster")


class RFPNotificationBroadcaster(RFPNotificationBroadcasterPort):
    """In-memory pub/sub SSE broadcaster with per-client asyncio.Queue fan-out and bounded ring buffer.

    Supports both async FastAPI route publication and synchronous background pipeline publication,
    assigns monotonically increasing SSE `id:` numbers, stores recent events in a bounded ring
    buffer (`maxlen=max_history`, default 256) for `Last-Event-ID` reconnection replay, and deduplicates
    by `ticket_id`.

    Note on bounded server deduplication:
    Server deduplication is bounded to `max_history` items to prevent unbounded memory growth in
    long-running processes. Even if a ticket ID evicts from the broadcaster's ring buffer after
    `max_history` subsequent events, client-side deduplication (`seenTicketIdsRef` in `useRFPNotifications`
    and `mergeAndDeduplicateTickets` in `rfpNotificationsClient`) provides a secondary layer of defense
    guaranteeing idempotency in the UI.
    """

    def __init__(self, max_history: int = 256, max_queue_size: int = 128) -> None:
        """Initialize broadcaster state with bounded replay ring buffer and thread lock."""
        self._max_history = max_history
        self._max_queue_size = max_queue_size
        self._lock = threading.Lock()
        self._sequence_counter: int = 0
        self._history: Deque[SSEEnvelope] = deque(maxlen=max_history)
        self._published_ticket_ids: Deque[str] = deque(maxlen=max_history)
        self._subscribers: Dict[
            int, Tuple[asyncio.Queue[SSEEnvelope], Optional[asyncio.AbstractEventLoop]]
        ] = {}

    def subscribe(self) -> asyncio.Queue[SSEEnvelope]:
        """Register a new SSE client subscriber and return its dedicated async queue."""
        queue: asyncio.Queue[SSEEnvelope] = asyncio.Queue(maxsize=self._max_queue_size)
        try:
            loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        with self._lock:
            self._subscribers[id(queue)] = (queue, loop)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[SSEEnvelope]) -> None:
        """Remove a disconnected SSE client subscriber queue cleanly."""
        with self._lock:
            self._subscribers.pop(id(queue), None)

    @property
    def active_subscriber_count(self) -> int:
        """Return the current number of active SSE subscribers."""
        with self._lock:
            return len(self._subscribers)

    def reset(self) -> None:
        """Clear replay history, sequence counter, and subscribers (intended for test isolation)."""
        with self._lock:
            self._sequence_counter = 0
            self._history.clear()
            self._published_ticket_ids.clear()
            self._subscribers.clear()

    def publish_ticket_created(
        self, event: RFPTicketCreatedEvent
    ) -> Optional[SSEEnvelope]:
        """Publish an `rfp_ticket_created` event to the replay buffer and all active subscribers.

        Deduplicates by `event.ticket_id` within the active history window so the same ticket
        is never broadcast twice.
        """
        with self._lock:
            if event.ticket_id in self._published_ticket_ids:
                logger.debug(
                    "Skipping duplicate rfp_ticket_created broadcast for ticket_id=%s",
                    event.ticket_id,
                )
                return None

            self._sequence_counter += 1
            envelope = SSEEnvelope(
                event_id=self._sequence_counter,
                event_name="rfp_ticket_created",
                ticket_id=event.ticket_id,
                payload=event,
                emitted_at=datetime.now(timezone.utc),
            )
            self._history.append(envelope)
            self._published_ticket_ids.append(event.ticket_id)
            subscribers_snapshot = list(self._subscribers.values())

        for queue, subscriber_loop in subscribers_snapshot:
            self._deliver_to_queue(queue, subscriber_loop, envelope)

        return envelope

    def _deliver_to_queue(
        self,
        queue: asyncio.Queue[SSEEnvelope],
        subscriber_loop: Optional[asyncio.AbstractEventLoop],
        envelope: SSEEnvelope,
    ) -> None:
        """Safely enqueue an envelope on a subscriber's queue across same-thread or cross-thread callers."""
        try:
            current_loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        def _put_nonblocking() -> None:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(envelope)
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

    def get_missed_events(
        self, last_event_id: Optional[str | int]
    ) -> List[SSEEnvelope]:
        """Return buffered SSE envelopes with `event_id > int(last_event_id)` for reconnection replay."""
        if last_event_id is None:
            return []

        raw_str = str(last_event_id).strip()
        if not raw_str:
            return []

        try:
            parsed_id = int(raw_str)
        except ValueError:
            return []

        with self._lock:
            return [env for env in self._history if env.event_id > parsed_id]

    def get_recent_events(self) -> List[SSEEnvelope]:
        """Return a snapshot of all buffered SSE envelopes in chronological order."""
        with self._lock:
            return list(self._history)

    def format_keep_alive(self) -> str:
        """Return a W3C SSE comment heartbeat frame (`: keep-alive\\n\\n`)."""
        return ": keep-alive\n\n"


_broadcaster_singleton: Optional[RFPNotificationBroadcaster] = None
_broadcaster_singleton_lock = threading.Lock()


def get_rfp_notification_broadcaster_singleton() -> RFPNotificationBroadcaster:
    """Return the process-wide singleton `RFPNotificationBroadcaster` instance."""
    global _broadcaster_singleton
    if _broadcaster_singleton is None:
        with _broadcaster_singleton_lock:
            if _broadcaster_singleton is None:
                _broadcaster_singleton = RFPNotificationBroadcaster()
    return _broadcaster_singleton
