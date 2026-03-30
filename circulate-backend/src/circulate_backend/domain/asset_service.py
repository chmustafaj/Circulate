"""Asset creation and snapshot freeze domain service."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from circulate_backend.domain.event_log_service import append_event
from circulate_backend.domain.events import DomainEvent
from circulate_backend.domain.hashing import hash_snapshot_payload
from circulate_backend.infra.db import get_sessionmaker
from circulate_backend.infra.db_models import Asset, AssetSnapshot, HashLog

log = structlog.get_logger(__name__)


class AssetNotFoundError(Exception):
    """Raised when asset does not exist."""

    pass


class AssetNotDraftError(Exception):
    """Raised when attempting to freeze a non-DRAFT asset."""

    pass


def create_asset() -> Asset:
    """Create a new asset in DRAFT status."""
    session_factory = get_sessionmaker()
    with session_factory() as session:
        asset = Asset(status="DRAFT")
        session.add(asset)
        session.commit()
        session.refresh(asset)

    log.info("asset.created", asset_id=str(asset.id), status=asset.status)
    return asset


def freeze_snapshot(asset_id: uuid.UUID, payload: dict[str, Any]) -> AssetSnapshot:
    """Freeze an asset snapshot. One-time operation; no re-freeze allowed.

    - Asset must exist and be DRAFT
    - Computes deterministic SHA256 hash of payload
    - Creates immutable AssetSnapshot row
    - Updates Asset status to FROZEN
    - Appends ASSET_SNAPSHOT_FROZEN event
    - Writes to hash_log for audit
    """
    session_factory = get_sessionmaker()
    with session_factory() as session:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise AssetNotFoundError(f"Asset {asset_id} not found")
        if asset.status != "DRAFT":
            raise AssetNotDraftError(f"Asset {asset_id} is {asset.status}, must be DRAFT")

        snapshot_hash = hash_snapshot_payload(payload)

        snapshot = AssetSnapshot(
            asset_id=asset_id,
            snapshot_version=1,
            snapshot_payload=payload,
            snapshot_hash_sha256=snapshot_hash,
        )
        session.add(snapshot)
        session.flush()  # Get snapshot.id for hash_log

        asset.status = "FROZEN"
        session.add(asset)

        hash_log_entry = HashLog(
            subject_type="asset_snapshot",
            subject_id=str(snapshot.id),
            sha256=snapshot_hash,
        )
        session.add(hash_log_entry)

        session.commit()
        session.refresh(snapshot)

    event = DomainEvent(
        event_type="ASSET_SNAPSHOT_FROZEN",
        aggregate_type="asset",
        aggregate_id=str(asset_id),
        payload={
            "snapshot_id": str(snapshot.id),
            "snapshot_hash_sha256": snapshot_hash,
            "snapshot_version": 1,
        },
    )
    append_event(event, publish=True)

    log.info(
        "asset_snapshot.frozen",
        asset_id=str(asset_id),
        snapshot_id=str(snapshot.id),
        snapshot_hash=snapshot_hash,
    )
    return snapshot
