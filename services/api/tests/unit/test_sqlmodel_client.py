"""Unit tests for decoupled SQLModel client manager and session provider."""

from sqlmodel import SQLModel, Session, select
from infrastructure.persistence.sqlmodel.client import (
    SQLModelClientManager,
    get_engine,
    init_db,
    get_db,
    sqlmodel_manager,
)


def test_sqlmodel_manager_default_sqlite_path() -> None:
    manager = SQLModelClientManager()
    path = manager.get_default_sqlite_path()
    assert path.endswith("inventory.db")


def test_sqlmodel_manager_build_url_fallback() -> None:
    manager = SQLModelClientManager()
    url = manager.build_database_url()
    assert "inventory.db" in url or "postgres" in url


def test_sqlmodel_manager_in_memory_engine() -> None:
    manager = SQLModelClientManager()
    engine = manager.create_engine("sqlite:///:memory:")
    assert str(engine.url) == "sqlite:///:memory:"

    manager.set_engine(engine)
    assert manager.get_engine() is engine


def test_sqlmodel_session_generator() -> None:
    manager = SQLModelClientManager()
    engine = manager.create_engine("sqlite:///:memory:")
    manager.set_engine(engine)

    session_gen = manager.get_session()
    session = next(session_gen)
    assert isinstance(session, Session)
    try:
        next(session_gen)
    except StopIteration:
        pass  # expected generator exhaustion


def test_sqlmodel_manager_custom_port(monkeypatch) -> None:
    monkeypatch.setenv("user", "test_user")
    monkeypatch.setenv("password", "test_pass")
    monkeypatch.setenv("host", "custom.pooler.supabase.com")
    monkeypatch.setenv("port", "6543")
    monkeypatch.setenv("dbname", "test_db")

    manager = SQLModelClientManager()
    url = manager.build_database_url()
    assert "@custom.pooler.supabase.com:6543/test_db" in url


def test_sqlmodel_manager_db_port_fallback(monkeypatch) -> None:
    monkeypatch.setenv("user", "test_user")
    monkeypatch.setenv("password", "test_pass")
    monkeypatch.setenv("host", "custom.pooler.supabase.com")
    monkeypatch.delenv("port", raising=False)
    monkeypatch.setenv("DB_PORT", "7654")
    monkeypatch.setenv("dbname", "test_db")

    manager = SQLModelClientManager()
    url = manager.build_database_url()
    assert "@custom.pooler.supabase.com:7654/test_db" in url


def test_sqlmodel_manager_default_port_fallback(monkeypatch) -> None:
    monkeypatch.setenv("user", "test_user")
    monkeypatch.setenv("password", "test_pass")
    monkeypatch.setenv("host", "custom.pooler.supabase.com")
    monkeypatch.delenv("port", raising=False)
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.setenv("dbname", "test_db")

    manager = SQLModelClientManager()
    url = manager.build_database_url()
    assert "@custom.pooler.supabase.com:5432/test_db" in url
