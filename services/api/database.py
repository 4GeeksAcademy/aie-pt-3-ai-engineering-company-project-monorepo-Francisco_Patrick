"""Database module exposing TinyDB and SQLModel engine and get_db session dependency.

Backward-compatible entry point for database services.
"""

from typing import Generator
from tinydb import TinyDB
from sqlmodel import Session

from infrastructure.database import (
    DATABASE_URL,
    engine,
    get_db,
    get_incidents_table,
    get_tinydb,
    init_db,
    sqlmodel_manager,
    tinydb_manager,
)

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
