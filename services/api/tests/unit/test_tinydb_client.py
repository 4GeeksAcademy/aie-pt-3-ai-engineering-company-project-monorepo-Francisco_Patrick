"""Unit tests for decoupled TinyDB connection manager client."""

import os
from tinydb import TinyDB
from infrastructure.persistence.tinydb.client import (
    TinyDBConnectionManager,
    get_tinydb,
    get_table,
    get_incidents_table,
    tinydb_manager,
)


def test_tinydb_manager_default_path() -> None:
    manager = TinyDBConnectionManager()
    default_path = manager.get_default_path()
    assert default_path.endswith("db.json")


def test_tinydb_manager_custom_path(tmp_path) -> None:
    custom_file = str(tmp_path / "custom_test.json")
    manager = TinyDBConnectionManager()
    client = manager.get_client(custom_file)
    assert isinstance(client, TinyDB)
    # Re-accessing same path returns same client instance
    assert manager.get_client(custom_file) is client

    # Clean up
    manager.close(custom_file)


def test_tinydb_manager_env_var(tmp_path, monkeypatch) -> None:
    env_file = str(tmp_path / "env_test.json")
    monkeypatch.setenv("TINYDB_PATH", env_file)

    manager = TinyDBConnectionManager()
    client = manager.get_client()
    assert isinstance(client, TinyDB)
    manager.close(env_file)


def test_tinydb_get_table(tmp_path) -> None:
    custom_file = str(tmp_path / "table_test.json")
    table = get_table("test_collection", db_path=custom_file)
    table.insert({"key": "value"})
    assert len(table.all()) == 1
    assert table.all()[0]["key"] == "value"
    tinydb_manager.close(custom_file)


def test_tinydb_close_all(tmp_path) -> None:
    f1 = str(tmp_path / "f1.json")
    f2 = str(tmp_path / "f2.json")
    manager = TinyDBConnectionManager()
    manager.get_client(f1)
    manager.get_client(f2)
    assert len(manager._instances) == 2
    manager.close_all()
    assert len(manager._instances) == 0
