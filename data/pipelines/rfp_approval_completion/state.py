"""LangGraph Part 3 state schema, checkpointer persistence, and structured execution tracer.

Implements:
- RFPApprovalState and DepartmentBranchApprovalState TypedDict schemas.
- Deterministic checkpointer thread ID namespacing (`rfp-{ticket_id}` and `rfp-{ticket_id}:{department_id}`).
- Persistent SQLite-backed LangGraph checkpointer (`SqliteSaver` / `PersistentSqliteCheckpointSaver`) using standard library `sqlite3` on top of LangGraph's `BaseCheckpointSaver`.
- Structured execution tracing hook (`record_execution_trace` and `traced_node`) logging `node_name`, `department_id`, `input_state`, `output_state`, and ISO-8601 `timestamp`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
import pickle
import sqlite3
import threading
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple, TypedDict, Union
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import InMemorySaver

DepartmentIdLiteral = Literal["warehouse", "lastmile", "reverse"]
ApprovalDecisionLiteral = Literal["approve", "reject", "request_changes"]
ApprovalStatusLiteral = Literal[
    "pending",
    "interrupted",
    "approved",
    "rejected",
    "changes_requested",
    "needs_human_review",
]


class ExecutionTraceEntryDict(TypedDict):
    """Serialized node execution trace record stored in graph state."""

    node_name: str
    department_id: Optional[str]
    input_state: Dict[str, Any]
    output_state: Dict[str, Any]
    timestamp: str


class DepartmentBranchApprovalState(TypedDict, total=False):
    """Scoped state for an individual department approval branch (`warehouse`, `lastmile`, `reverse`)."""

    ticket_id: str
    department_id: DepartmentIdLiteral
    department_name: str
    responsible_person: str
    rfp_metadata: Dict[str, Any]
    key_aspects: Dict[str, Any]
    open_questions: List[str]
    policy_warnings: List[str]
    draft_content: str
    evaluation_results: List[Dict[str, Any]]
    approval_status: str
    approver: Optional[str]
    review_feedback: Optional[str]
    iteration_count: int
    max_revisions: int
    approved_at: Optional[str]
    escalation_note: Optional[str]
    execution_trace: List[ExecutionTraceEntryDict]


class RFPApprovalState(TypedDict, total=False):
    """Top-level Part 3 approval, arbitration, and final synthesis graph state."""

    ticket_id: str
    ticket_status: str
    raw_pdf_path: str
    active_departments: List[DepartmentIdLiteral]
    rfp_metadata: Dict[str, Any]
    department_sections: Dict[str, Dict[str, Any]]
    arbitration_logs: List[Dict[str, Any]]
    final_document: Optional[Dict[str, Any]]
    max_revisions: int
    execution_trace: List[ExecutionTraceEntryDict]


DEPARTMENT_LEADS: Dict[DepartmentIdLiteral, Tuple[str, str]] = {
    "warehouse": ("Warehouse Operations", "Ana Whitfield"),
    "lastmile": ("Last Mile and Carrier Management", "Carlos Vega"),
    "reverse": ("Reverse Logistics", "Sofía Ramos"),
}

COMMERCIAL_DIRECTOR = "Miguel Torres"
REVERSE_LOGISTICS_LEAD = "Sofía Ramos"


def format_ticket_thread_id(ticket_id: Union[UUID, str]) -> str:
    """Build deterministic parent checkpointer thread ID for an RFP ticket."""
    return f"rfp-{str(ticket_id)}"


def format_branch_thread_id(ticket_id: Union[UUID, str], department_id: str) -> str:
    """Build deterministic namespaced checkpointer thread ID for a specific department branch."""
    return f"rfp-{str(ticket_id)}:{department_id}"


def make_branch_config(ticket_id: Union[UUID, str], department_id: str) -> RunnableConfig:
    """Create RunnableConfig scoped to a department branch thread ID."""
    return {
        "configurable": {
            "thread_id": format_branch_thread_id(ticket_id, department_id),
        }
    }


def make_ticket_config(ticket_id: Union[UUID, str]) -> RunnableConfig:
    """Create RunnableConfig scoped to the parent ticket thread ID."""
    return {
        "configurable": {
            "thread_id": format_ticket_thread_id(ticket_id),
        }
    }


def _summarize_snapshot(data: Any) -> Dict[str, Any]:
    """Create a concise, JSON-serializable snapshot of node input or output state for execution tracing."""
    if not isinstance(data, dict):
        return {"value": str(data)}

    summary: Dict[str, Any] = {}
    for key, val in data.items():
        if key == "execution_trace":
            continue
        if isinstance(val, (str, int, float, bool)) or val is None:
            if isinstance(val, str) and len(val) > 300:
                summary[key] = val[:300] + "..."
            else:
                summary[key] = val
        elif isinstance(val, (list, tuple)):
            summary[key] = f"list(len={len(val)})" if len(val) > 5 else list(val)
        elif isinstance(val, dict):
            summary[key] = {
                str(k): (
                    v[:120] + "..."
                    if isinstance(v, str) and len(v) > 120
                    else v
                )
                for k, v in list(val.items())[:10]
                if not isinstance(v, (dict, list))
            }
        else:
            summary[key] = str(val)
    return summary


def record_execution_trace(
    state: Dict[str, Any],
    node_name: str,
    input_snapshot: Dict[str, Any],
    output_snapshot: Dict[str, Any],
    department_id: Optional[str] = None,
) -> List[ExecutionTraceEntryDict]:
    """Append an immutable ExecutionTraceEntryDict to state's execution_trace list."""
    existing = list(state.get("execution_trace") or [])
    dept = department_id or state.get("department_id")
    entry: ExecutionTraceEntryDict = {
        "node_name": node_name,
        "department_id": str(dept) if dept else None,
        "input_state": _summarize_snapshot(input_snapshot),
        "output_state": _summarize_snapshot(output_snapshot),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    existing.append(entry)
    return existing


def traced_node(
    node_name: str,
    department_id: Optional[str] = None,
) -> Callable[[Callable[..., Dict[str, Any]]], Callable[..., Dict[str, Any]]]:
    """Decorator wrapping a LangGraph node function or method to automatically record execution traces."""

    def decorator(
        fn: Callable[..., Dict[str, Any]]
    ) -> Callable[..., Dict[str, Any]]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            if len(args) >= 2 and isinstance(args[1], dict):
                state: Dict[str, Any] = args[1]
            elif len(args) >= 1 and isinstance(args[0], dict):
                state = args[0]
            else:
                state = kwargs.get("state") or {}

            input_snap = _summarize_snapshot(state)
            updates = fn(*args, **kwargs) or {}
            output_snap = _summarize_snapshot(updates)
            merged_trace = record_execution_trace(
                state=state,
                node_name=node_name,
                input_snapshot=input_snap,
                output_snapshot=output_snap,
                department_id=department_id or state.get("department_id"),
            )
            result = dict(updates)
            result["execution_trace"] = merged_trace
            return result

        return wrapper

    return decorator


class SqliteSaver(InMemorySaver):
    """Persistent SQLite-backed LangGraph checkpointer compatible with `interrupt()` and `Command(resume=...)`.

    Persists LangGraph's `storage`, `writes`, and `blobs` dictionaries atomically to an SQLite database
    table per thread_id so checkpoints survive across process restarts and checkpointer instances.
    """

    def __init__(self, db_path: Union[str, Path] = ":memory:") -> None:
        super().__init__()
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_sqlite()
        self._load_all_from_sqlite()

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            return self._conn
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_sqlite(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
                        thread_id TEXT PRIMARY KEY,
                        storage_blob BLOB NOT NULL,
                        writes_blob BLOB NOT NULL,
                        blobs_blob BLOB NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                if self.db_path != ":memory:":
                    conn.close()

    def _load_all_from_sqlite(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT thread_id, storage_blob, writes_blob, blobs_blob FROM langgraph_checkpoints"
                )
                for thread_id, s_blob, w_blob, b_blob in cursor.fetchall():
                    s_data = pickle.loads(s_blob)
                    w_data = pickle.loads(w_blob)
                    b_data = pickle.loads(b_blob)
                    self.storage[thread_id].update(s_data)
                    for k, v in w_data.items():
                        self.writes[k].update(v)
                    self.blobs.update(b_data)
            finally:
                if self.db_path != ":memory:":
                    conn.close()

    def _persist_thread(self, thread_id: str) -> None:
        with self._lock:
            s_data = dict(self.storage.get(thread_id, {}))
            w_data = {
                k: dict(v)
                for k, v in self.writes.items()
                if isinstance(k, tuple) and len(k) > 0 and k[0] == thread_id
            }
            b_data = {
                k: v
                for k, v in self.blobs.items()
                if isinstance(k, tuple) and len(k) > 0 and k[0] == thread_id
            }
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO langgraph_checkpoints (thread_id, storage_blob, writes_blob, blobs_blob, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(thread_id) DO UPDATE SET
                        storage_blob = excluded.storage_blob,
                        writes_blob = excluded.writes_blob,
                        blobs_blob = excluded.blobs_blob,
                        updated_at = excluded.updated_at
                    """,
                    (
                        thread_id,
                        pickle.dumps(s_data),
                        pickle.dumps(w_data),
                        pickle.dumps(b_data),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
            finally:
                if self.db_path != ":memory:":
                    conn.close()

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        if self.db_path != ":memory:":
            self._load_all_from_sqlite()
        return super().get_tuple(config)

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        next_config = super().put(config, checkpoint, metadata, new_versions)
        thread_id = str(config["configurable"]["thread_id"])
        self._persist_thread(thread_id)
        return next_config

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        super().put_writes(config, writes, task_id, task_path)
        thread_id = str(config["configurable"]["thread_id"])
        self._persist_thread(thread_id)


_DEFAULT_CHECKPOINTER: Optional[SqliteSaver] = None
_CHECKPOINTER_LOCK = threading.Lock()


def get_default_checkpointer(db_path: Optional[Union[str, Path]] = None) -> SqliteSaver:
    """Return or initialize the shared persistent checkpointer instance."""
    global _DEFAULT_CHECKPOINTER
    if db_path is not None:
        return SqliteSaver(db_path=db_path)
    with _CHECKPOINTER_LOCK:
        if _DEFAULT_CHECKPOINTER is None:
            default_file = (
                Path(__file__).resolve().parents[3]
                / "services"
                / "api"
                / "rfp_checkpoints.sqlite"
            )
            _DEFAULT_CHECKPOINTER = SqliteSaver(db_path=default_file)
        return _DEFAULT_CHECKPOINTER
