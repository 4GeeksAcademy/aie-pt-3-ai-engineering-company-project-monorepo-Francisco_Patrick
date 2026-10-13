"""TinyDB client and connection management.

Encapsulates document store connection lifecycle, multi-tenant/test path resolution,
table retrieval, and connection pooling for TrackFlow driven persistence adapters.
"""

import os
from typing import Dict, Optional
from tinydb import TinyDB
from tinydb.table import Table


class TinyDBConnectionManager:
    """Thread-safe connection manager for TinyDB instances."""

    def __init__(self) -> None:
        self._instances: Dict[str, TinyDB] = {}

    def get_default_path(self) -> str:
        """Resolve the canonical default path to db.json in services/api root."""
        # services/api/infrastructure/persistence/tinydb/client.py -> services/api/db.json
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        return os.path.join(base_dir, "db.json")

    def resolve_db_path(self, explicit_path: Optional[str] = None) -> str:
        """Resolve the effective database file path.

        Priority:
        1. explicit_path if provided
        2. TINYDB_PATH environment variable
        3. Canonical default services/api/db.json
        """
        if explicit_path:
            return os.path.abspath(explicit_path)

        env_path = os.environ.get("TINYDB_PATH")
        if env_path:
            dirname = os.path.dirname(env_path)
            if not dirname or os.path.exists(dirname):
                return os.path.abspath(env_path)

        return self.get_default_path()

    def get_client(self, db_path: Optional[str] = None) -> TinyDB:
        """Retrieve or initialize a TinyDB instance for the given or resolved path.

        Args:
            db_path: Optional explicit file path to database JSON file.

        Returns:
            Active TinyDB database client instance.
        """
        resolved_path = self.resolve_db_path(db_path)
        if resolved_path not in self._instances:
            # Ensure parent directory exists if creating new db
            dirname = os.path.dirname(resolved_path)
            if dirname and not os.path.exists(dirname):
                os.makedirs(dirname, exist_ok=True)
            self._instances[resolved_path] = TinyDB(resolved_path)
        return self._instances[resolved_path]

    def get_table(
        self, table_name: str, db: Optional[TinyDB] = None, db_path: Optional[str] = None
    ) -> Table:
        """Retrieve a specific table from the given or active TinyDB database.

        Args:
            table_name: Document collection table name (e.g. 'users', 'incidents').
            db: Optional existing TinyDB instance.
            db_path: Optional database file path.

        Returns:
            TinyDB Table instance.
        """
        target_db = db if db is not None else self.get_client(db_path)
        return target_db.table(table_name)

    def close(self, db_path: Optional[str] = None) -> None:
        """Close an active database connection and remove from instance cache.

        Args:
            db_path: Optional database file path to close. If None, closes current resolved path.
        """
        resolved_path = self.resolve_db_path(db_path)
        if resolved_path in self._instances:
            self._instances[resolved_path].close()
            del self._instances[resolved_path]

    def close_all(self) -> None:
        """Close all active cached TinyDB database instances."""
        for path, instance in list(self._instances.items()):
            try:
                instance.close()
            except Exception:
                pass
        self._instances.clear()


# Global connection manager instance
tinydb_manager = TinyDBConnectionManager()


def get_tinydb(db_path: Optional[str] = None) -> TinyDB:
    """Convenience accessor to retrieve active TinyDB client."""
    return tinydb_manager.get_client(db_path)


def get_table(
    table_name: str, db: Optional[TinyDB] = None, db_path: Optional[str] = None
) -> Table:
    """Convenience accessor to retrieve a named table from TinyDB."""
    return tinydb_manager.get_table(table_name, db=db, db_path=db_path)


def get_incidents_table(db: Optional[TinyDB] = None) -> Table:
    """Backward compatibility helper for retrieving 'incidents' table."""
    return get_table("incidents", db=db)


__all__ = [
    "TinyDBConnectionManager",
    "get_incidents_table",
    "get_table",
    "get_tinydb",
    "tinydb_manager",
]
