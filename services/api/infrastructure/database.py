import os
from typing import Generator
from tinydb import TinyDB
from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv

import models  # noqa: F401

load_dotenv()

# --- TinyDB Connection (Auth & Users) ---
_tinydb_instances = {}

def get_tinydb() -> TinyDB:
    """Returns TinyDB client instance for users and authentication."""
    db_path = os.environ.get("TINYDB_PATH", os.path.join(os.path.dirname(__file__), "..", "db.json"))
    if db_path not in _tinydb_instances:
        _tinydb_instances[db_path] = TinyDB(db_path)
    return _tinydb_instances[db_path]


def get_incidents_table(db_instance: TinyDB = None):
    """Returns the incidents table from TinyDB."""
    target_db = db_instance if db_instance is not None else get_tinydb()
    return target_db.table("incidents")


# --- Supabase / SQLModel Engine Connection (Inventory & Orders) ---
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./inventory.db")

# Fix legacy connection string prefix if present
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db(target_engine=None) -> None:
    """Initializes SQLModel table schemas in Supabase/database."""
    import models
    eng = target_engine if target_engine is not None else engine
    SQLModel.metadata.create_all(eng)


def get_db() -> Generator[Session, None, None]:
    """Dependency injection yielding an SQLModel session per request."""
    with Session(engine) as session:
        yield session
