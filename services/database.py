"""Services level database re-export facade."""

import os
import sys

_API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "api"))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from services.api.database import (
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
