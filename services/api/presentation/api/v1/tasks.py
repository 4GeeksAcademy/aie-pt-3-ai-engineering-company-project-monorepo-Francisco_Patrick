"""Task inspection controller for tracking asynchronous task progress and results."""

from datetime import datetime, timezone
import logging
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, status

from infrastructure.queue import celery_app, get_enqueued_task_meta
from infrastructure.queue.dlq import sanitize_error_message
from infrastructure.queue.schemas import TaskStatusEnum, TaskStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Query Task Lifecycle Status & Result",
    description="Queries the execution state and computed output payload of an asynchronous background job.",
    responses={
        200: {"model": TaskStatusResponse, "description": "Task found and status reported."},
        404: {"description": "Task identifier unknown or unsubmitted."},
    },
)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """Inspect and resolve current status of a background task."""
    meta = get_enqueued_task_meta(task_id)
    async_res = celery_app.AsyncResult(task_id)

    created_at = None
    if meta and "enqueued_at" in meta:
        try:
            created_at = datetime.fromisoformat(meta["enqueued_at"])
        except Exception:
            created_at = None

    try:
        state = str(async_res.state).upper()
        is_ready = async_res.ready()
    except Exception as backend_err:
        logger.warning(f"Redis backend error for task {task_id}: {backend_err}")
        if meta is not None:
            return TaskStatusResponse(
                task_id=task_id,
                status=TaskStatusEnum.PENDING,
                result=None,
                error=None,
                created_at=created_at,
                completed_at=None,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue service is temporarily unavailable. Please retry shortly.",
        )

    # In Celery Redis backend, an unknown ID defaults to PENDING.
    # Disambiguate: if meta is missing and result backend hasn't recorded success/failure, reject as 404.
    if meta is None and not is_ready and state == "PENDING":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )

    if state == "SUCCESS":
        return TaskStatusResponse(
            task_id=task_id,
            status=TaskStatusEnum.SUCCESS,
            result=async_res.result,
            error=None,
            created_at=created_at,
            completed_at=datetime.now(timezone.utc),
        )
    elif state in ("FAILURE", "REVOKED"):
        raw_error = str(async_res.result) if async_res.result is not None else "Task execution failed"
        sanitized_error = sanitize_error_message(raw_error)
        return TaskStatusResponse(
            task_id=task_id,
            status=TaskStatusEnum.FAILURE,
            result=None,
            error=sanitized_error,
            created_at=created_at,
            completed_at=datetime.now(timezone.utc),
        )
    elif state == "STARTED":
        return TaskStatusResponse(
            task_id=task_id,
            status=TaskStatusEnum.STARTED,
            result=None,
            error=None,
            created_at=created_at,
            completed_at=None,
        )
    else:
        # Default pending state
        return TaskStatusResponse(
            task_id=task_id,
            status=TaskStatusEnum.PENDING,
            result=None,
            error=None,
            created_at=created_at,
            completed_at=None,
        )
