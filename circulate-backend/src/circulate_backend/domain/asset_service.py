"""Asset creation, draft snapshot updates, and snapshot freeze domain service."""

from __future__ import annotations

import uuid
from typing import Any, Tuple

import structlog
from sqlalchemy import select

from circulate_backend.domain.event_log_service import append_event
from circulate_backend.domain.events import DomainEvent
from circulate_backend.domain.hashing import hash_snapshot_payload
from circulate_backend.domain.valuation.calculator import (
    AttestationOutOfRangeError,
    MissingValuationInputError,
    RulesetKeyError,
    compute_fair_max,
)
from circulate_backend.domain.valuation.enums import ValuationMethod
from circulate_backend.domain.valuation.ruleset_loader import load_ruleset
from circulate_backend.infra.db import get_sessionmaker
from circulate_backend.infra.db_models import Asset, AssetSnapshot, HashLog, utcnow as db_utcnow

log = structlog.get_logger(__name__)


class AssetNotFoundError(Exception):
    """Raised when asset does not exist."""

    pass


class AssetNotDraftError(Exception):
    """Raised when attempting to modify a non-DRAFT asset or snapshot."""

    pass


class AssetSnapshotNotFoundError(Exception):
    """Raised when no asset_snapshots row exists for the asset."""

    pass


def create_asset() -> Tuple[Asset, AssetSnapshot]:
    """Create a new asset in DRAFT status with an initial DRAFT snapshot row.

    The snapshot has empty JSON payload until PATCH merges fields or freeze completes it.
    """
    session_factory = get_sessionmaker()
    with session_factory() as session:
        asset = Asset(status="DRAFT")
        session.add(asset)
        session.flush()

        snapshot = AssetSnapshot(
            asset_id=asset.id,
            snapshot_version=1,
            status="DRAFT",
            snapshot_payload={},
            snapshot_hash_sha256=None,
            frozen_at=None,
        )
        session.add(snapshot)
        session.commit()
        session.refresh(asset)
        session.refresh(snapshot)

    log.info(
        "asset.created",
        asset_id=str(asset.id),
        snapshot_id=str(snapshot.id),
        status=asset.status,
    )
    return asset, snapshot


def get_asset(asset_id: uuid.UUID) -> Asset:
    """Retrieve an asset by ID."""
    session_factory = get_sessionmaker()
    with session_factory() as session:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise AssetNotFoundError(f"Asset {asset_id} not found")
        session.expunge(asset)
    return asset


def get_asset_snapshot(asset_id: uuid.UUID) -> AssetSnapshot:
    """Return the single snapshot row for this asset (DRAFT or FROZEN)."""
    session_factory = get_sessionmaker()
    with session_factory() as session:
        stmt = select(AssetSnapshot).where(AssetSnapshot.asset_id == asset_id)
        snapshot = session.scalars(stmt).first()
        if snapshot is None:
            raise AssetSnapshotNotFoundError(f"No snapshot for asset {asset_id}")
        session.expunge(snapshot)
    return snapshot


def update_draft_snapshot(asset_id: uuid.UUID, draft_data: dict[str, Any]) -> AssetSnapshot:
    """Merge partial data into the DRAFT snapshot_payload. Asset and snapshot must be DRAFT."""
    session_factory = get_sessionmaker()
    with session_factory() as session:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise AssetNotFoundError(f"Asset {asset_id} not found")
        if asset.status != "DRAFT":
            raise AssetNotDraftError(f"Asset {asset_id} is {asset.status}, must be DRAFT")

        stmt = select(AssetSnapshot).where(
            AssetSnapshot.asset_id == asset_id,
            AssetSnapshot.status == "DRAFT",
        )
        snapshot = session.scalars(stmt).first()
        if snapshot is None:
            raise AssetSnapshotNotFoundError(f"No DRAFT snapshot for asset {asset_id}")

        existing = dict(snapshot.snapshot_payload or {})
        existing.update(draft_data)
        snapshot.snapshot_payload = existing
        session.commit()
        session.refresh(snapshot)

    log.info("asset_snapshot.draft_updated", asset_id=str(asset_id), snapshot_id=str(snapshot.id))
    return snapshot


def _build_snapshot_payload(
    freeze_data: dict[str, Any],
    fair_max_result: Any,
    ruleset: dict[str, Any],
) -> dict[str, Any]:
    """Build the final snapshot payload that will be hashed and persisted."""
    payload: dict[str, Any] = {
        "valuation_method": freeze_data["valuation_method"],
        "category": freeze_data["category"],
        "condition": freeze_data["condition"],
        "photo_urls": freeze_data["photo_urls"],
        "fair_max_cents": fair_max_result.fair_max_cents,
        "fair_max_min_cents": fair_max_result.min_cents,
        "fair_max_max_cents": fair_max_result.max_cents,
        "fair_max_baseline_cents": fair_max_result.baseline_cents,
        "valuation_ruleset_version": fair_max_result.ruleset_version,
        "attestation_applied": fair_max_result.attestation_applied,
    }

    if freeze_data.get("serial_number") is not None:
        payload["serial_number"] = freeze_data["serial_number"]
    if freeze_data.get("materials_description") is not None:
        payload["materials_description"] = freeze_data["materials_description"]
    if freeze_data.get("attested_fair_max_cents") is not None:
        payload["attested_fair_max_cents"] = freeze_data["attested_fair_max_cents"]

    if freeze_data["valuation_method"] == ValuationMethod.metal.value:
        metal = freeze_data["metal"]
        payload["metal_profile"] = metal["metal_profile"]
        payload["weight_mg"] = metal["weight_mg"]
        payload["stone_deduction_mg"] = metal.get("stone_deduction_mg", 0)
    elif freeze_data["valuation_method"] == ValuationMethod.merchandise.value:
        product_inputs = freeze_data["merchandise"]
        cat = freeze_data["category"]
        sub = product_inputs["subcategory"]
        anchor_key = f"{cat}.{sub}"
        materials_baseline = ruleset["category_anchors_cents"][anchor_key]
        rate_fab = ruleset["time_rates"]["fabrication_cents_per_minute"]
        rate_skill = ruleset["time_rates"]["skill_cents_per_minute"]
        fab_m = product_inputs["fabrication_minutes"]
        sk_m = product_inputs["skill_minutes"]
        payload["subcategory"] = sub
        payload["fabrication_minutes"] = fab_m
        payload["skill_minutes"] = sk_m
        payload["materials_baseline_cents"] = materials_baseline
        payload["rate_fabrication_cents_per_minute"] = rate_fab
        payload["rate_skill_cents_per_minute"] = rate_skill
        payload["fabrication_time_value_cents"] = fab_m * rate_fab
        payload["skill_time_value_cents"] = sk_m * rate_skill

    return payload


def freeze_snapshot(asset_id: uuid.UUID, freeze_data: dict[str, Any]) -> AssetSnapshot:
    """Freeze the DRAFT snapshot: compute Fair-Max, hash, set FROZEN.

    Updates the existing asset_snapshots row in place (DRAFT → FROZEN).
    """
    ruleset = load_ruleset()

    metal_data = freeze_data.get("metal") or {}
    product_data = freeze_data.get("merchandise") or {}

    fair_max_result = compute_fair_max(
        valuation_method=ValuationMethod(freeze_data["valuation_method"]),
        category=freeze_data["category"],
        condition=freeze_data["condition"],
        metal_profile=metal_data.get("metal_profile"),
        weight_mg=metal_data.get("weight_mg"),
        stone_deduction_mg=metal_data.get("stone_deduction_mg", 0),
        subcategory=product_data.get("subcategory"),
        fabrication_minutes=product_data.get("fabrication_minutes"),
        skill_minutes=product_data.get("skill_minutes"),
        attested_fair_max_cents=freeze_data.get("attested_fair_max_cents"),
        ruleset=ruleset,
    )

    snapshot_payload = _build_snapshot_payload(freeze_data, fair_max_result, ruleset)
    snapshot_hash = hash_snapshot_payload(snapshot_payload)

    session_factory = get_sessionmaker()
    with session_factory() as session:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise AssetNotFoundError(f"Asset {asset_id} not found")
        if asset.status != "DRAFT":
            raise AssetNotDraftError(f"Asset {asset_id} is {asset.status}, must be DRAFT")

        stmt = select(AssetSnapshot).where(
            AssetSnapshot.asset_id == asset_id,
            AssetSnapshot.status == "DRAFT",
        )
        snapshot = session.scalars(stmt).first()
        if snapshot is None:
            raise AssetSnapshotNotFoundError(f"No DRAFT snapshot for asset {asset_id}")

        snapshot.snapshot_payload = snapshot_payload
        snapshot.snapshot_hash_sha256 = snapshot_hash
        snapshot.frozen_at = db_utcnow()
        snapshot.status = "FROZEN"
        session.add(snapshot)

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
            "snapshot_version": snapshot.snapshot_version,
            "fair_max_cents": fair_max_result.fair_max_cents,
            "fair_max_min_cents": fair_max_result.min_cents,
            "fair_max_max_cents": fair_max_result.max_cents,
            "valuation_ruleset_version": fair_max_result.ruleset_version,
        },
    )
    append_event(event, publish=True)

    log.info(
        "asset_snapshot.frozen",
        asset_id=str(asset_id),
        snapshot_id=str(snapshot.id),
        snapshot_hash=snapshot_hash,
        fair_max_cents=fair_max_result.fair_max_cents,
    )
    return snapshot
