"""Dedicated TinyDB persistence adapter for immutable Agent Memory Audit Logs (T007).

Implements `MemoryAuditLogRepositoryPort` in dedicated TinyDB document storage,
recording every proposal transition (`proposed`, `approved`, `rejected`, `edited`,
`discarded`, `evicted`) with complete attribution (FR-014, SC-006).
"""

import os
import threading
from typing import List, Optional

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from domain.agent.entities import MemoryAuditLogEntry
from domain.agent.exceptions import MemoryStorageError
from domain.agent.ports import MemoryAuditLogRepositoryPort


class TinyDBMemoryAuditLogRepository(MemoryAuditLogRepositoryPort):
    """Append-only TinyDB repository for immutable memory lifecycle audit records."""

    def __init__(
        self,
        db: Optional[TinyDB] = None,
        db_path: Optional[str] = None,
        table_name: str = "memory_audit_logs",
    ) -> None:
        """Initialize the dedicated TinyDB memory audit log repository.

        Args:
            db: Optional existing TinyDB instance.
            db_path: Optional explicit file path for dedicated JSON storage.
            table_name: Document table name (defaults to `'memory_audit_logs'`).
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
            env_path = os.environ.get("MEMORY_AUDIT_LOG_DB_PATH")
            if env_path:
                resolved = os.path.abspath(env_path)
                dirname = os.path.dirname(resolved)
                if dirname and not os.path.exists(dirname):
                    os.makedirs(dirname, exist_ok=True)
                self._db = TinyDB(resolved)
            else:
                self._db = TinyDB(storage=MemoryStorage)

        self._table = self._db.table(table_name)

    def record_entry(self, entry: MemoryAuditLogEntry) -> None:
        """Append an immutable audit entry to the audit log store."""
        try:
            with self._lock:
                self._table.insert(entry.to_dict())
        except Exception as exc:
            raise MemoryStorageError(
                f"Failed to record memory audit log entry: {exc}"
            ) from exc

    def list_entries(
        self,
        proposal_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryAuditLogEntry]:
        """Query audit log entries ordered newest first."""
        try:
            with self._lock:
                clamped_limit = max(1, min(200, int(limit if limit is not None else 50)))
                all_docs = self._table.all()
                entries: List[MemoryAuditLogEntry] = []

                for doc in all_docs:
                    entry = MemoryAuditLogEntry.from_dict(dict(doc))
                    if proposal_id is not None and entry.proposal_id != proposal_id:
                        continue
                    if event_type is not None and entry.event_type != event_type:
                        continue
                    entries.append(entry)

                # Order newest first (preserving reverse insertion order on ties)
                entries.reverse()
                entries.sort(key=lambda e: e.timestamp, reverse=True)
                return entries[:clamped_limit]
        except Exception as exc:
            raise MemoryStorageError(
                f"Failed to list memory audit log entries: {exc}"
            ) from exc

    def clear(self) -> None:
        """Clear audit log records (for test isolation only)."""
        with self._lock:
            self._table.truncate()


__all__ = ["TinyDBMemoryAuditLogRepository"]
