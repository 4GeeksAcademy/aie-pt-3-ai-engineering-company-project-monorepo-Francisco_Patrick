"""TinyDB driven persistence adapters package."""

from infrastructure.persistence.tinydb.audit_log_repository import TinyDBAuditLogRepository
from infrastructure.persistence.tinydb.client import (
    TinyDBConnectionManager,
    get_incidents_table,
    get_table,
    get_tinydb,
    tinydb_manager,
)
from infrastructure.persistence.tinydb.incident_repository import TinyDBIncidentRepository
from infrastructure.persistence.tinydb.password_reset_repository import (
    TinyDBPasswordResetTokenRepository,
)
from infrastructure.persistence.tinydb.profile_repository import TinyDBProfileRepository
from infrastructure.persistence.tinydb.supplier_repository import TinyDBSupplierRepository
from infrastructure.persistence.tinydb.user_repository import TinyDBUserRepository

__all__ = [
    "TinyDBAuditLogRepository",
    "TinyDBConnectionManager",
    "TinyDBIncidentRepository",
    "TinyDBPasswordResetTokenRepository",
    "TinyDBProfileRepository",
    "TinyDBSupplierRepository",
    "TinyDBUserRepository",
    "get_incidents_table",
    "get_table",
    "get_tinydb",
    "tinydb_manager",
]
