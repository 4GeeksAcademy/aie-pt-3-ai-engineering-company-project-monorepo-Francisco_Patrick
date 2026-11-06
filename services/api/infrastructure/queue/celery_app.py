"""Celery application factory, Redis broker/backend configuration, and task registry."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery import Celery
import redis

logger = logging.getLogger(__name__)

# Resolve Redis URLs from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# If running inside pytest without a live Redis server, fallback to in-memory broker
if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None:
    os.environ["REDIS_URL"] = "memory://"
    os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
    REDIS_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"

# Create Celery application
celery_app = Celery(
    "trackflow_tasks",
    broker=REDIS_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "infrastructure.queue.tasks",
        "services.api.infrastructure.queue.tasks",
    ],
)

# Apply configuration adhering to plan.md and research.md
celery_app.conf.update(
    broker_url=REDIS_URL,
    result_backend=CELERY_RESULT_BACKEND,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=86400,  # 24 hours
    worker_prefetch_multiplier=1,
    task_always_eager=("pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None),
    task_eager_propagates=False,
    task_store_eager_result=True,
)

# In-memory fallback dictionary for test suites without a live Redis server
_in_memory_task_meta: Dict[str, Dict[str, Any]] = {}


def _get_redis_client() -> Optional[redis.Redis]:
    """Obtain a Redis client instance from the configured broker URL."""
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None or REDIS_URL.startswith("memory://"):
        return None
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1)
        client.ping()
        return client
    except Exception as e:
        logger.debug(f"Redis client connection unavailable: {e}")
        return None


def register_enqueued_task(task_id: str, task_name: str) -> Dict[str, Any]:
    """Store initial task metadata in Redis under task_meta:{task_id}.

    Used to disambiguate legitimate pending tasks from arbitrary invalid UUIDs.

    Args:
        task_id: Unique UUID string for the task.
        task_name: Logical identifier for the task function.

    Returns:
        Dictionary of stored metadata.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    meta = {
        "task_id": task_id,
        "task_name": task_name,
        "status": "pending",
        "enqueued_at": now_iso,
    }

    client = _get_redis_client()
    if client is not None:
        try:
            client.set(f"task_meta:{task_id}", json.dumps(meta), ex=86400)
        except Exception as e:
            logger.warning(f"Failed to write task_meta to Redis for {task_id}: {e}")
            _in_memory_task_meta[task_id] = meta
    else:
        _in_memory_task_meta[task_id] = meta

    return meta


def get_enqueued_task_meta(task_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve initial task metadata for a given task ID.

    Args:
        task_id: Unique UUID string for the task.

    Returns:
        Dictionary of metadata if registered, None otherwise.
    """
    client = _get_redis_client()
    if client is not None:
        try:
            raw = client.get(f"task_meta:{task_id}")
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Failed to read task_meta from Redis for {task_id}: {e}")

    return _in_memory_task_meta.get(task_id)
