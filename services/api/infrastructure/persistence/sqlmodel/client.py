"""SQLModel client, engine configuration, and session management.

Provides decoupled database engine creation, PostgreSQL/SQLite connection fallback,
schema initialization, and session generator dependency for relational persistence adapters.
"""

import os
import sys
import urllib.parse
from typing import Generator, Optional, Union
from dotenv import load_dotenv
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.engine import Engine, make_url

# Anchor dotenv loading to services/api/.env
_api_env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
)
if os.path.exists(_api_env_path):
    load_dotenv(dotenv_path=_api_env_path, override=False)
else:
    load_dotenv()

# If running inside test runner, ensure Celery Redis URLs don't override in-memory test configuration
if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None:
    os.environ["REDIS_URL"] = "memory://"
    os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
    if not os.getenv("TEST_USE_REMOTE_DB"):
        os.environ.pop("user", None)
        os.environ.pop("DB_USER", None)
        os.environ.pop("host", None)
        os.environ.pop("DB_HOST", None)



class SQLModelClientManager:
    """Manages SQLModel relational database engine lifecycle and session yielding."""

    def __init__(self) -> None:
        self._engine: Optional[Engine] = None

    def get_default_sqlite_path(self) -> str:
        """Resolve canonical default path to inventory.db in services/api root."""
        # services/api/infrastructure/persistence/sqlmodel/client.py -> services/api/inventory.db
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        return os.path.join(base_dir, "inventory.db")

    def build_database_url(self) -> str:
        """Construct database connection URL from environment variables with SQLite fallback."""
        if ("pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None) and not os.getenv("TEST_USE_REMOTE_DB"):
            test_sqlite_path = os.path.join(
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
                "test_inventory.db",
            )
            return f"sqlite:///{test_sqlite_path}"

        db_user = os.getenv("user") or os.getenv("DB_USER")
        db_password = os.getenv("password") or os.getenv("DB_PASSWORD")
        db_host = os.getenv("host") or os.getenv("DB_HOST")
        db_port = os.getenv("port") or os.getenv("DB_PORT", "5432")
        db_name = os.getenv("dbname") or os.getenv("DB_NAME", "postgres")

        default_sqlite_url = f"sqlite:///{self.get_default_sqlite_path()}"

        if db_user and db_host:
            encoded_password = urllib.parse.quote_plus(db_password or "")
            url = f"postgresql+psycopg2://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?sslmode=require"
        else:
            url = os.environ.get("DATABASE_URL", default_sqlite_url)

        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

        return url

    def create_engine(self, database_url: Optional[str] = None) -> Engine:
        """Create a SQLAlchemy / SQLModel engine with resilient fallback to SQLite."""
        url = database_url or self.build_database_url()
        default_sqlite_url = f"sqlite:///{self.get_default_sqlite_path()}"

        if not url.startswith("sqlite"):
            target_host = "unknown"
            target_port: Union[int, str] = "unknown"
            try:
                parsed_url = make_url(url)
                if parsed_url.host:
                    target_host = parsed_url.host
                if parsed_url.port:
                    target_port = parsed_url.port
            except Exception:
                pass

            if target_host == "unknown":
                target_host = os.getenv("host") or os.getenv("DB_HOST") or "unknown"
            if target_port == "unknown":
                target_port = (
                    os.getenv("port")
                    or os.getenv("DB_PORT")
                    or (5432 if "postgres" in url else "unknown")
                )

            try:
                test_engine = create_engine(
                    url, echo=False, connect_args={"connect_timeout": 3}
                )
                with test_engine.connect():
                    pass
                print(
                    f"[INFO] Database connection succeeded (host: {target_host}, port: {target_port})."
                )
                return test_engine
            except Exception as e:
                print(
                    f"[WARNING] Database connection failed (host: {target_host}, port: {target_port}): {e}. "
                    f"Falling back to SQLite: {default_sqlite_url}"
                )
                return create_engine(
                    default_sqlite_url,
                    echo=False,
                    connect_args={"check_same_thread": False},
                )

        return create_engine(
            url, echo=False, connect_args={"check_same_thread": False}
        )

    def get_engine(self) -> Engine:
        """Retrieve or initialize the singleton database engine."""
        if self._engine is None:
            self._engine = self.create_engine()
        return self._engine

    def set_engine(self, custom_engine: Engine) -> None:
        """Set a custom database engine (e.g. for testing with in-memory SQLite)."""
        self._engine = custom_engine

    def _ensure_columns_exist(self, eng: Engine) -> None:
        """Add any missing columns to existing tables for seamless backward compatibility."""
        from sqlalchemy import inspect, text

        try:
            insp = inspect(eng)
            table_names = insp.get_table_names()

            alter_statements = []
            if "sku" in table_names:
                existing_cols = {c["name"] for c in insp.get_columns("sku")}
                if "client_name" not in existing_cols:
                    alter_statements.append("ALTER TABLE sku ADD COLUMN client_name VARCHAR DEFAULT 'PureStep Footwear'")
                if "category" not in existing_cols:
                    alter_statements.append("ALTER TABLE sku ADD COLUMN category VARCHAR DEFAULT 'fashion'")
                if "warehouse" not in existing_cols:
                    alter_statements.append("ALTER TABLE sku ADD COLUMN warehouse VARCHAR DEFAULT 'LA'")
                if "warehouse_id" not in existing_cols:
                    alter_statements.append("ALTER TABLE sku ADD COLUMN warehouse_id VARCHAR DEFAULT 'LA'")

            if "stock_entry" in table_names:
                existing_cols = {c["name"] for c in insp.get_columns("stock_entry")}
                if "warehouse" not in existing_cols:
                    alter_statements.append("ALTER TABLE stock_entry ADD COLUMN warehouse VARCHAR DEFAULT 'LA'")
                if "warehouse_id" not in existing_cols:
                    alter_statements.append("ALTER TABLE stock_entry ADD COLUMN warehouse_id VARCHAR DEFAULT 'LA'")
                if "reference" not in existing_cols:
                    alter_statements.append("ALTER TABLE stock_entry ADD COLUMN reference VARCHAR DEFAULT ''")

            if "stock_exit" in table_names:
                existing_cols = {c["name"] for c in insp.get_columns("stock_exit")}
                if "warehouse" not in existing_cols:
                    alter_statements.append("ALTER TABLE stock_exit ADD COLUMN warehouse VARCHAR DEFAULT 'LA'")
                if "warehouse_id" not in existing_cols:
                    alter_statements.append("ALTER TABLE stock_exit ADD COLUMN warehouse_id VARCHAR DEFAULT 'LA'")
                if "exit_type" not in existing_cols:
                    alter_statements.append("ALTER TABLE stock_exit ADD COLUMN exit_type VARCHAR DEFAULT 'dispatch'")
                if "tracking_number" not in existing_cols:
                    alter_statements.append("ALTER TABLE stock_exit ADD COLUMN tracking_number VARCHAR DEFAULT NULL")

            if "department_sections" in table_names:
                existing_cols = {c["name"] for c in insp.get_columns("department_sections")}
                if "draft_content" not in existing_cols:
                    alter_statements.append("ALTER TABLE department_sections ADD COLUMN draft_content TEXT DEFAULT NULL")
                if "iteration" not in existing_cols:
                    alter_statements.append("ALTER TABLE department_sections ADD COLUMN iteration INTEGER DEFAULT 0")
                if "status" not in existing_cols:
                    alter_statements.append("ALTER TABLE department_sections ADD COLUMN status VARCHAR DEFAULT 'pending'")
                if "evaluation_results" not in existing_cols:
                    alter_statements.append("ALTER TABLE department_sections ADD COLUMN evaluation_results JSON DEFAULT '[]'")
                if "approval_status" not in existing_cols:
                    alter_statements.append("ALTER TABLE department_sections ADD COLUMN approval_status VARCHAR DEFAULT 'pending'")
                if "approver" not in existing_cols:
                    alter_statements.append("ALTER TABLE department_sections ADD COLUMN approver VARCHAR DEFAULT NULL")
                if "review_feedback" not in existing_cols:
                    alter_statements.append("ALTER TABLE department_sections ADD COLUMN review_feedback TEXT DEFAULT NULL")
                if "approved_at" not in existing_cols:
                    alter_statements.append("ALTER TABLE department_sections ADD COLUMN approved_at TIMESTAMP DEFAULT NULL")
                if "updated_at" not in existing_cols:
                    alter_statements.append("ALTER TABLE department_sections ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

            if alter_statements:
                with eng.connect() as conn:
                    for stmt in alter_statements:
                        try:
                            conn.execute(text(stmt))
                            conn.commit()
                        except Exception:
                            pass
        except Exception:
            pass

    def init_db(self, target_engine: Optional[Engine] = None) -> None:
        """Initialize SQLModel table schemas with resilient fallback."""
        from infrastructure.persistence.sqlmodel.models import (  # noqa: F401
            SKU,
            StockEntry,
            StockExit,
            TelemetryEventRecord,
            IntakeTicketTable,
            RFPMetadataTable,
            DepartmentSectionTable,
            IntakeHandoffPayloadTable,
            Part3HandoffPayloadTable,
            ArbitrationLogTable,
            FinalDocumentTable,
        )
        from infrastructure.queue.models import DeadLetterQueueRecord  # noqa: F401

        eng = target_engine if target_engine is not None else self.get_engine()
        default_sqlite_url = f"sqlite:///{self.get_default_sqlite_path()}"

        try:
            SQLModel.metadata.create_all(eng)
            self._ensure_columns_exist(eng)
        except Exception as e:
            if not str(eng.url).startswith("sqlite"):
                host = eng.url.host or os.getenv("host") or os.getenv("DB_HOST") or "unknown"
                port = eng.url.port or os.getenv("port") or os.getenv("DB_PORT") or (5432 if "postgres" in str(eng.url) else "unknown")
                print(
                    f"[WARNING] Schema creation failed (host: {host}, port: {port}, "
                    f"url: {eng.url.render_as_string(hide_password=True)}): {e}"
                )
                print(f"[INFO] Falling back to local SQLite engine: {default_sqlite_url}")
                fallback_eng = create_engine(
                    default_sqlite_url,
                    echo=False,
                    connect_args={"check_same_thread": False},
                )
                self.set_engine(fallback_eng)
                SQLModel.metadata.create_all(fallback_eng)
                self._ensure_columns_exist(fallback_eng)
            else:
                raise e

    def get_session(self) -> Generator[Session, None, None]:
        """FastAPI dependency yielding an SQLModel session per request."""
        eng = self.get_engine()
        with Session(eng) as session:
            yield session


# Global client manager instance
sqlmodel_manager = SQLModelClientManager()
engine = sqlmodel_manager.get_engine()


def get_engine() -> Engine:
    """Retrieve active database engine."""
    return sqlmodel_manager.get_engine()


def init_db(target_engine: Optional[Engine] = None) -> None:
    """Initialize SQLModel table schemas."""
    sqlmodel_manager.init_db(target_engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency injection yielding an SQLModel session."""
    yield from sqlmodel_manager.get_session()


__all__ = [
    "SQLModelClientManager",
    "engine",
    "get_db",
    "get_engine",
    "init_db",
    "sqlmodel_manager",
]
