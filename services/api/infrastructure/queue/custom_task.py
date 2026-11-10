"""Custom base Celery task with exponential retries and dead letter queue routing."""

import logging
from typing import Any, Tuple
from celery import Task

from infrastructure.queue.dlq import dlq_adapter

logger = logging.getLogger(__name__)


class TrackFlowTask(Task):
    """Base Celery task providing automatic retries, backoff, and DLQ quarantine on failure."""

    autoretry_for: Tuple[type[Exception], ...] = (Exception,)
    max_retries: int = 3
    retry_backoff: bool = True
    retry_backoff_max: int = 600
    retry_jitter: bool = True
    acks_late: bool = True
    reject_on_worker_lost: bool = True

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: Tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Hook called when a task fails permanently or exhausts all retry attempts."""
        attempt_number = self.request.retries if hasattr(self.request, "retries") else self.max_retries
        # If retried 3 times, attempt number is 3
        effective_attempt = max(1, attempt_number)

        payload_ref = None
        if args:
            payload_ref = str(args)[:255]
        elif kwargs:
            payload_ref = str(kwargs)[:255]

        logger.error(
            f"[DLQ] Task {self.name} (id: {task_id}) failed permanently after "
            f"{effective_attempt} attempts. Quarantining to Dead Letter Queue: {exc}"
        )

        try:
            dlq_adapter.record_failure(
                task_id=task_id,
                task_name=self.name,
                attempt_number=effective_attempt,
                error_message=str(exc),
                payload_reference=payload_ref,
            )
        except Exception as dlq_err:
            logger.critical(f"Failed to persist failure record to DLQ database: {dlq_err}")

        super().on_failure(exc, task_id, args, kwargs, einfo)

