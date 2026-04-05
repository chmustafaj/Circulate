"""Tests for asset creation, draft snapshot updates, and snapshot freeze."""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from circulate_backend.domain.asset_service import (
    AssetNotDraftError,
    AssetNotFoundError,
    create_asset,
    freeze_snapshot,
    get_asset,
    get_asset_snapshot,
    update_draft_snapshot,
)
from circulate_backend.domain.valuation.calculator import AttestationOutOfRangeError
from circulate_backend.infra import db as db_module
from circulate_backend.infra.asset_snapshot_immutability import install_asset_snapshot_immutability
from circulate_backend.infra.db import Base
from circulate_backend.infra.db_models import AssetSnapshot

METAL_FREEZE_PAYLOAD = {
    "valuation_method": "metal",
    "category": "jewelry",
    "condition": "good",
    "metal": {
        "metal_profile": "gold_14k",
        "weight_mg": 24300,
        "stone_deduction_mg": 0,
    },
    "photo_urls": ["https://example.com/watch-1.jpg"],
}

MERCH_FREEZE_PAYLOAD = {
    "valuation_method": "merchandise",
    "category": "jewelry",
    "condition": "excellent",
    "merchandise": {
        "subcategory": "wristwatch",
        "fabrication_minutes": 100,
        "skill_minutes": 200,
    },
    "photo_urls": ["https://example.com/watch-1.jpg"],
}


@pytest.fixture
def sqlite_session(monkeypatch):
    """Use sqlite in-memory for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    install_asset_snapshot_immutability(engine)
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


# ── Create ──────────────────────────────────────────────────────────────


def test_create_asset(sqlite_session) -> None:
    """Create asset returns DRAFT asset and DRAFT snapshot."""
    asset, snapshot = create_asset()
    assert asset.id is not None
    assert asset.status == "DRAFT"
    assert snapshot.status == "DRAFT"
    assert snapshot.snapshot_payload == {}
    assert snapshot.snapshot_hash_sha256 is None
    assert snapshot.frozen_at is None


# ── Draft snapshot updates ────────────────────────────────────────────


def test_update_draft_snapshot(sqlite_session) -> None:
    """PATCH merges data into snapshot_payload."""
    asset, _ = create_asset()
    updated = update_draft_snapshot(asset.id, {"category": "jewelry", "condition": "good"})
    assert updated.snapshot_payload["category"] == "jewelry"
    assert updated.snapshot_payload["condition"] == "good"


def test_update_draft_snapshot_merges(sqlite_session) -> None:
    """Successive patches merge, not replace."""
    asset, _ = create_asset()
    update_draft_snapshot(asset.id, {"category": "jewelry"})
    updated = update_draft_snapshot(asset.id, {"condition": "good"})
    assert updated.snapshot_payload["category"] == "jewelry"
    assert updated.snapshot_payload["condition"] == "good"


def test_update_draft_rejects_frozen(sqlite_session) -> None:
    """PATCH on a FROZEN asset raises."""
    asset, _ = create_asset()
    freeze_snapshot(asset.id, METAL_FREEZE_PAYLOAD)
    with pytest.raises(AssetNotDraftError, match="FROZEN"):
        update_draft_snapshot(asset.id, {"condition": "fair"})


def test_get_asset_and_snapshot(sqlite_session) -> None:
    """GET returns snapshot payload from asset_snapshots."""
    asset, snap = create_asset()
    update_draft_snapshot(asset.id, {"category": "electronics"})
    fetched = get_asset(asset.id)
    s = get_asset_snapshot(asset.id)
    assert fetched.status == "DRAFT"
    assert s.id == snap.id
    assert s.snapshot_payload["category"] == "electronics"


def test_get_asset_not_found(sqlite_session) -> None:
    """GET raises for non-existent asset."""
    with pytest.raises(AssetNotFoundError, match="not found"):
        get_asset(uuid.uuid4())


# ── Freeze — metal path ─────────────────────────────────────────────────


def test_freeze_metal_success(sqlite_session) -> None:
    """Freeze with metal inputs computes Fair-Max and updates same snapshot row."""
    asset, snap_before = create_asset()
    assert snap_before.status == "DRAFT"
    snapshot = freeze_snapshot(asset.id, METAL_FREEZE_PAYLOAD)
    assert snapshot.id == snap_before.id
    assert snapshot.status == "FROZEN"
    assert snapshot.snapshot_hash_sha256
    assert len(snapshot.snapshot_hash_sha256) == 64
    assert snapshot.snapshot_version == 1
    assert snapshot.frozen_at is not None

    stored = snapshot.snapshot_payload
    assert stored["fair_max_cents"] == 109350
    assert stored["fair_max_min_cents"] == 85050
    assert stored["fair_max_max_cents"] == 139725
    assert stored["valuation_ruleset_version"] == "2026-04-01"
    assert stored["attestation_applied"] is False


def test_freeze_metal_with_attestation(sqlite_session) -> None:
    """Attested value within range is accepted."""
    asset, _ = create_asset()
    payload = {**METAL_FREEZE_PAYLOAD, "attested_fair_max_cents": 100000}
    snapshot = freeze_snapshot(asset.id, payload)
    stored = snapshot.snapshot_payload
    assert stored["fair_max_cents"] == 100000
    assert stored["attestation_applied"] is True


def test_freeze_metal_attestation_out_of_range(sqlite_session) -> None:
    """Attested value outside range is rejected."""
    asset, _ = create_asset()
    payload = {**METAL_FREEZE_PAYLOAD, "attested_fair_max_cents": 999999}
    with pytest.raises(AttestationOutOfRangeError):
        freeze_snapshot(asset.id, payload)


# ── Freeze — merchandise path ──────────────────────────────────────────


def test_freeze_merchandise_success(sqlite_session) -> None:
    """Freeze with merchandise inputs computes Fair-Max (materials + time rates)."""
    asset, _ = create_asset()
    snapshot = freeze_snapshot(asset.id, MERCH_FREEZE_PAYLOAD)
    stored = snapshot.snapshot_payload
    assert stored["fair_max_cents"] == 520000
    assert stored["fair_max_min_cents"] == 260000
    assert stored["fair_max_max_cents"] == 676000
    assert stored["materials_baseline_cents"] == 500000
    assert stored["fabrication_time_value_cents"] == 5000
    assert stored["skill_time_value_cents"] == 15000


# ── Freeze — general guards ────────────────────────────────────────────


def test_freeze_asset_not_found(sqlite_session) -> None:
    """Freeze raises for non-existent asset."""
    with pytest.raises(AssetNotFoundError, match="not found"):
        freeze_snapshot(uuid.uuid4(), METAL_FREEZE_PAYLOAD)


def test_freeze_rejects_re_freeze(sqlite_session) -> None:
    """Freeze raises for already FROZEN asset."""
    asset, _ = create_asset()
    freeze_snapshot(asset.id, METAL_FREEZE_PAYLOAD)
    with pytest.raises(AssetNotDraftError, match="FROZEN"):
        freeze_snapshot(asset.id, METAL_FREEZE_PAYLOAD)


def test_freeze_deterministic_hash(sqlite_session) -> None:
    """Same inputs produce same hash across two assets."""
    a1, _ = create_asset()
    s1 = freeze_snapshot(a1.id, METAL_FREEZE_PAYLOAD)
    a2, _ = create_asset()
    s2 = freeze_snapshot(a2.id, METAL_FREEZE_PAYLOAD)
    assert s1.snapshot_hash_sha256 == s2.snapshot_hash_sha256


# ── DB-level immutability ───────────────────────────────────────────────


def test_frozen_snapshot_rejects_update_at_db_layer(sqlite_session) -> None:
    """Triggers block UPDATE on rows with frozen_at set."""
    asset, _ = create_asset()
    snapshot = freeze_snapshot(asset.id, METAL_FREEZE_PAYLOAD)
    session = sqlite_session()
    row = session.get(AssetSnapshot, snapshot.id)
    assert row is not None
    t = dict(row.snapshot_payload)
    t["fair_max_cents"] = 1
    row.snapshot_payload = t
    with pytest.raises(DBAPIError, match="cannot update frozen asset_snapshot"):
        session.commit()
    session.rollback()


def test_frozen_snapshot_rejects_delete_at_db_layer(sqlite_session) -> None:
    """Triggers block DELETE on rows with frozen_at set."""
    asset, _ = create_asset()
    snapshot = freeze_snapshot(asset.id, METAL_FREEZE_PAYLOAD)
    session = sqlite_session()
    row = session.get(AssetSnapshot, snapshot.id)
    assert row is not None
    session.delete(row)
    with pytest.raises(DBAPIError, match="cannot delete frozen asset_snapshot"):
        session.commit()
    session.rollback()


def test_draft_snapshot_allows_update_at_db_layer(sqlite_session) -> None:
    """DRAFT rows (frozen_at NULL) can be updated at DB layer."""
    asset, snap = create_asset()
    session = sqlite_session()
    row = session.get(AssetSnapshot, snap.id)
    row.snapshot_payload = {"category": "jewelry"}
    session.commit()
    session.refresh(row)
    assert row.snapshot_payload == {"category": "jewelry"}
