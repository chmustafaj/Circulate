"""Tests for asset creation and snapshot freeze."""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from circulate_backend.domain.asset_service import (
    AssetNotDraftError,
    AssetNotFoundError,
    create_asset,
    freeze_snapshot,
)
from circulate_backend.infra import db as db_module
from circulate_backend.infra.db import Base


@pytest.fixture
def sqlite_session(monkeypatch):
    """Use sqlite in-memory for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(db_module, "get_engine", lambda: engine)
    monkeypatch.setattr(db_module, "get_sessionmaker", lambda: SessionLocal)
    monkeypatch.setattr(
        "circulate_backend.domain.asset_service.get_sessionmaker", lambda: SessionLocal
    )
    monkeypatch.setattr(
        "circulate_backend.domain.event_log_service.get_sessionmaker", lambda: SessionLocal
    )
    monkeypatch.delenv("REDIS_URL", raising=False)
    return SessionLocal


def test_create_asset(sqlite_session) -> None:
    """Create asset returns DRAFT asset."""
    asset = create_asset()
    assert asset.id is not None
    assert asset.status == "DRAFT"


def test_freeze_snapshot_success(sqlite_session) -> None:
    """Freeze creates snapshot with deterministic hash."""
    asset = create_asset()
    payload = {
        "fair_max_cents": 80000,
        "category": "jewelry",
        "serial_number": "SN-12345",
        "materials": "gold",
        "condition": "good",
        "photo_urls": ["https://example.com/watch-1.jpg"],
    }
    snapshot = freeze_snapshot(asset.id, payload)
    assert snapshot.id is not None
    assert snapshot.snapshot_hash_sha256
    assert len(snapshot.snapshot_hash_sha256) == 64
    assert snapshot.snapshot_version == 1


def test_freeze_snapshot_asset_not_found(sqlite_session) -> None:
    """Freeze raises for non-existent asset."""
    with pytest.raises(AssetNotFoundError, match="not found"):
        freeze_snapshot(
            uuid.uuid4(),
            {
                "fair_max_cents": 80000,
                "serial_number": "SN-404",
                "materials": "gold",
                "condition": "good",
                "photo_urls": ["https://example.com/watch-1.jpg"],
            },
        )


def test_freeze_snapshot_rejects_re_freeze(sqlite_session) -> None:
    """Freeze raises for already FROZEN asset."""
    asset = create_asset()
    freeze_snapshot(
        asset.id,
        {
            "fair_max_cents": 80000,
            "serial_number": "SN-12345",
            "materials": "gold",
            "condition": "good",
            "photo_urls": ["https://example.com/watch-1.jpg"],
        },
    )
    with pytest.raises(AssetNotDraftError, match="FROZEN"):
        freeze_snapshot(
            asset.id,
            {
                "fair_max_cents": 90000,
                "serial_number": "SN-12345",
                "materials": "gold",
                "condition": "good",
                "photo_urls": ["https://example.com/watch-2.jpg"],
            },
        )


def test_freeze_snapshot_rejects_floats(sqlite_session) -> None:
    """Freeze rejects payload with floats."""
    asset = create_asset()
    with pytest.raises(ValueError, match="floating-point"):
        freeze_snapshot(
            asset.id,
            {
                "fair_max_cents": 800.50,
                "serial_number": "SN-12345",
                "materials": "gold",
                "condition": "good",
                "photo_urls": ["https://example.com/watch-1.jpg"],
            },
        )
