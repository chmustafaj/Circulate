import os
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# Create shared sqlite engine and patch db BEFORE app import (conftest loads first)
# Use file path to avoid sqlite :memory: per-connection isolation issues
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
_test_engine = create_engine(f"sqlite:///{_test_db_path}")
_test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

import circulate_backend.infra.db_models  # noqa: F401 - register models with Base
from circulate_backend.infra.db import Base

Base.metadata.create_all(bind=_test_engine)

import circulate_backend.infra.db as db_module

db_module.get_engine = lambda: _test_engine
db_module.get_sessionmaker = lambda: _test_session_factory


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")


@pytest.fixture(autouse=True)
def _reset_db(monkeypatch):
    """Clear REDIS_URL and reset tables between tests for isolation."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    yield
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)

