"""Snapshot verification service."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from circulate_backend.domain.hashing import hash_snapshot_payload
from circulate_backend.infra.db import get_sessionmaker
from circulate_backend.infra.db_models import AssetSnapshot

log = structlog.get_logger(__name__)


class SnapshotNotFoundError(Exception):
    """Raised when snapshot does not exist."""

    pass


def verify_snapshot_payload(snapshot_id: uuid.UUID, payload: dict[str, Any]) -> bool:
    """Verify that the given payload matches the stored snapshot hash."""
    session_factory = get_sessionmaker()
    with session_factory() as session:
        snapshot = session.get(AssetSnapshot, snapshot_id)
        if snapshot is None:
            raise SnapshotNotFoundError(f"Snapshot {snapshot_id} not found")

        computed_hash = hash_snapshot_payload(payload)
        valid = computed_hash == snapshot.snapshot_hash_sha256

    log.info(
        "snapshot.verified",
        snapshot_id=str(snapshot_id),
        valid=valid,
    )
    return valid


def get_snapshot_for_verification(snapshot_id: uuid.UUID) -> tuple[str, dict[str, Any]]:
    """Return stored hash and payload for client-side verification."""
    session_factory = get_sessionmaker()
    with session_factory() as session:
        snapshot = session.get(AssetSnapshot, snapshot_id)
        if snapshot is None:
            raise SnapshotNotFoundError(f"Snapshot {snapshot_id} not found")

        return snapshot.snapshot_hash_sha256, dict(snapshot.snapshot_payload)
