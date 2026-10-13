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
