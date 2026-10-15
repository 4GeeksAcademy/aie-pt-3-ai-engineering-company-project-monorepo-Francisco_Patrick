"""Infrastructure database package - Backward compatibility facade.

Delegates persistence connections to dedicated driven adapters:
- TinyDB: infrastructure.persistence.tinydb.client
- SQLModel: infrastructure.persistence.sqlmodel.client
"""

import os
from typing import Generator
from tinydb import TinyDB
from sqlmodel import Session
from dotenv import load_dotenv

import models  # noqa: F401
from infrastructure.persistence.tinydb.client import (
    get_incidents_table as _tinydb_get_incidents_table,
    get_tinydb as _tinydb_get_tinydb,
    tinydb_manager,
)
from infrastructure.persistence.sqlmodel.client import (
    engine as _sqlmodel_engine,
    get_db as _sqlmodel_get_db,
    init_db as _sqlmodel_init_db,
    sqlmodel_manager,
)

load_dotenv()

# --- TinyDB Connection (Auth, Users, Incidents, Suppliers) ---
def get_tinydb() -> TinyDB:
    """Returns TinyDB client instance for users and authentication."""
    return _tinydb_get_tinydb()


def get_incidents_table(db_instance: TinyDB = None):
    """Returns the incidents table from TinyDB."""
    return _tinydb_get_incidents_table(db=db_instance)


# --- Supabase / SQLModel Engine Connection (Inventory & Orders) ---
engine = _sqlmodel_engine
DATABASE_URL = sqlmodel_manager.build_database_url()


def init_db(target_engine=None) -> None:
    """Initializes SQLModel table schemas in Supabase/database with resilient fallback."""
    _sqlmodel_init_db(target_engine=target_engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency injection yielding an SQLModel session per request."""
    yield from _sqlmodel_get_db()


__all__ = [
    "DATABASE_URL",
    "engine",
    "get_db",
    "get_incidents_table",
    "get_tinydb",
    "init_db",
    "sqlmodel_manager",
    "tinydb_manager",
]
