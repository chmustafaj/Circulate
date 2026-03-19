import os
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from circulate_backend.domain.event_log_service import append_event
from circulate_backend.domain.events import DomainEvent
from circulate_backend.infra import db as db_module
from circulate_backend.infra.db import Base


def test_append_event_sqlite(monkeypatch) -> None:
    # Use sqlite in-memory to test the write path without requiring Postgres.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(db_module, "get_engine", lambda: engine)
    monkeypatch.setattr(db_module, "get_sessionmaker", lambda: SessionLocal)
    monkeypatch.delenv("REDIS_URL", raising=False)

    event = DomainEvent(
        event_id=uuid.uuid4(),
        event_type="TEST_EVENT",
        aggregate_type="test",
        aggregate_id="abc",
        payload={"x": 1},
    )

    created = append_event(event, publish=True)
    assert created.event_id == event.event_id

