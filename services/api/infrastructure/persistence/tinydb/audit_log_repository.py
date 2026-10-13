"""TinyDB persistence adapter for security audit logs.

Implements AuditLogRepositoryPort using TinyDB document store.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
from tinydb import TinyDB

from domain.auth.ports import AuditLogRepositoryPort
from infrastructure.persistence.tinydb.client import get_table, get_tinydb


class TinyDBAuditLogRepository(AuditLogRepositoryPort):
    """TinyDB document store adapter implementing AuditLogRepositoryPort."""

    def __init__(self, db: Optional[TinyDB] = None, table_name: str = "audit_logs") -> None:
        """Initialize audit log repository with TinyDB table."""
        self._db = db if db is not None else get_tinydb()
        self.table = get_table(table_name, db=self._db)

    def log_event(
        self,
        event_type: str,
        user_id: Optional[str],
        ip_address: str,
        details: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record immutable security audit log event."""
        doc = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.table.insert(doc)
        return doc


__all__ = ["TinyDBAuditLogRepository"]
