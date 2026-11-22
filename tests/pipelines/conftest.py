"""Shared pytest fixtures for TrackFlow RFP agentic pipelines (Parts 1, 2, and 3)."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Generator

import pytest
from sqlmodel import Session, create_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_approval_completion.state import SqliteSaver  # noqa: E402
from infrastructure.persistence.sqlmodel.client import init_db  # noqa: E402
from infrastructure.persistence.sqlmodel.rfp_repository import (  # noqa: E402
    SQLModelIntakeTicketRepository,
)


@pytest.fixture
def sqlite_checkpointer(tmp_path: Path) -> SqliteSaver:
    """Provide an isolated SQLite-backed LangGraph checkpointer per test."""
    checkpoint_file = tmp_path / "test_checkpoints.sqlite"
    return SqliteSaver(db_path=checkpoint_file)


@pytest.fixture
def rfp_db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Provide an isolated SQLModel SQLite session with all RFP tables initialized."""
    db_file = tmp_path / "test_rfp_part3.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    init_db(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def rfp_repository(rfp_db_session: Session) -> SQLModelIntakeTicketRepository:
    """Provide an SQLModelIntakeTicketRepository bound to the isolated test session."""
    return SQLModelIntakeTicketRepository(rfp_db_session)
