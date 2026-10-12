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
    default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db.json"))
    db_path = os.environ.get("TINYDB_PATH", default_path)
    dirname = os.path.dirname(db_path)
    if dirname and not os.path.exists(dirname):
        db_path = default_path
    if db_path not in _tinydb_instances:
        _tinydb_instances[db_path] = TinyDB(db_path)
    return _tinydb_instances[db_path]


def get_incidents_table(db_instance: TinyDB = None):
    """Returns the incidents table from TinyDB."""
    target_db = db_instance if db_instance is not None else get_tinydb()
    return target_db.table("incidents")


import urllib.parse

# --- Supabase / SQLModel Engine Connection (Inventory & Orders) ---
db_user = os.getenv("user") or os.getenv("DB_USER")
db_password = os.getenv("password") or os.getenv("DB_PASSWORD")
db_host = os.getenv("host") or os.getenv("DB_HOST")
db_port = os.getenv("port") or os.getenv("DB_PORT", "5432")
db_name = os.getenv("dbname") or os.getenv("DB_NAME", "postgres")

if db_user and db_host:
    encoded_password = urllib.parse.quote_plus(db_password or "")
    DATABASE_URL = f"postgresql+psycopg2://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?sslmode=require"
else:
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./inventory.db")

# Fix legacy connection string prefix if present
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Absolute path fallback for local SQLite
default_sqlite_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inventory.db"))
default_sqlite_url = f"sqlite:///{default_sqlite_path}"

def _create_database_engine():
    global DATABASE_URL
    url = None
    if db_user and db_host:
        encoded_password = urllib.parse.quote_plus(db_password or "")
        url = f"postgresql+psycopg2://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?sslmode=require"
    else:
        url = os.environ.get("DATABASE_URL", default_sqlite_url)
    
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    if not url.startswith("sqlite"):
        try:
            test_engine = create_engine(url, echo=False, connect_args={"connect_timeout": 3})
            with test_engine.connect():
                pass
            return test_engine
        except Exception as e:
            target_host = db_host or url.split("@")[-1].split("/")[0]
            print(f"[WARNING] Database connection to {target_host} failed ({e}). Proactively falling back to SQLite: {default_sqlite_url}")
            return create_engine(default_sqlite_url, echo=False, connect_args={"check_same_thread": False})
    
    return create_engine(url, echo=False, connect_args={"check_same_thread": False})

engine = _create_database_engine()


def init_db(target_engine=None) -> None:
    """Initializes SQLModel table schemas in Supabase/database with resilient fallback."""
    global engine
    import models
    eng = target_engine if target_engine is not None else engine
    try:
        SQLModel.metadata.create_all(eng)
    except Exception as e:
        if not str(eng.url).startswith("sqlite"):
            print(f"[WARNING] Schema creation failed on {eng.url.render_as_string(hide_password=True)}: {e}")
            print(f"[INFO] Falling back to local SQLite engine: {default_sqlite_url}")
            engine = create_engine(default_sqlite_url, echo=False, connect_args={"check_same_thread": False})
            SQLModel.metadata.create_all(engine)
        else:
            raise e


def get_db() -> Generator[Session, None, None]:
    """Dependency injection yielding an SQLModel session per request."""
    with Session(engine) as session:
        yield session
