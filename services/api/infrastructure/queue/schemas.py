"""Pydantic schemas and DTOs for queue tasks and lifecycle management."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class TaskStatusEnum(str, Enum):
    """Lifecycle states of an asynchronous task."""

    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"


class AsyncTaskAcceptedResponse(BaseModel):
    """Response returned with HTTP 202 Accepted when a task is enqueued."""

    model_config = ConfigDict(from_attributes=True)

    task_id: str = Field(description="Unique tracking identifier for the enqueued task.")
    status: str = Field(default="pending", description="Initial lifecycle state ('pending').")
    message: str = Field(description="Human-readable acknowledgement.")
    poll_url: str = Field(description="Relative endpoint path to query task progress.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of submission.",
    )


class TaskStatusResponse(BaseModel):
    """Response returned by GET /tasks/{task_id} describing execution status."""

    model_config = ConfigDict(from_attributes=True)

    task_id: str = Field(description="Unique identifier of the task.")
    status: TaskStatusEnum = Field(description="Current lifecycle status.")
    result: Optional[Any] = Field(
        default=None,
        description="Output payload produced upon successful completion. Null otherwise.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Sanitized error message if task failed. Null otherwise.",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp of task enqueue.",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp of completion or terminal failure.",
    )

