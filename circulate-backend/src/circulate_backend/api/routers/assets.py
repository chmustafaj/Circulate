"""Assets API router."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from circulate_backend.api.schemas.snapshot import DraftUpdateRequest, FreezeRequest
from circulate_backend.domain.asset_service import (
    AssetNotDraftError,
    AssetNotFoundError,
    AssetSnapshotNotFoundError,
    create_asset,
    freeze_snapshot,
    get_asset,
    get_asset_snapshot,
    update_draft_snapshot,
)
from circulate_backend.domain.valuation.calculator import (
    AttestationOutOfRangeError,
    MissingValuationInputError,
    RulesetKeyError,
)

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("")
def create_asset_endpoint() -> dict:
    """Create a new asset in DRAFT status with an initial DRAFT snapshot row."""
    asset, snapshot = create_asset()
    return {
        "asset_id": str(asset.id),
        "status": asset.status,
        "snapshot_id": str(snapshot.id),
        "snapshot_status": snapshot.status,
    }


@router.get("/{asset_id}")
def get_asset_endpoint(asset_id: UUID) -> dict:
    """Retrieve an asset and its snapshot (payload is empty until PATCH or freeze)."""
    try:
        asset = get_asset(asset_id)
        snapshot = get_asset_snapshot(asset_id)
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AssetSnapshotNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {
        "asset_id": str(asset.id),
        "status": asset.status,
        "snapshot_id": str(snapshot.id),
        "snapshot_status": snapshot.status,
        "snapshot_payload": snapshot.snapshot_payload,
    }


@router.patch("/{asset_id}")
def update_draft_snapshot_endpoint(asset_id: UUID, body: DraftUpdateRequest) -> dict:
    """Merge fields into the DRAFT snapshot_payload. Only while snapshot is DRAFT."""
    try:
        snapshot = update_draft_snapshot(asset_id, body.model_dump(mode="json", exclude_none=True))
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AssetNotDraftError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except AssetSnapshotNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {
        "asset_id": str(asset_id),
        "snapshot_id": str(snapshot.id),
        "snapshot_status": snapshot.status,
        "snapshot_payload": snapshot.snapshot_payload,
    }


@router.post("/{asset_id}/freeze")
def freeze_snapshot_endpoint(asset_id: UUID, payload: FreezeRequest) -> dict:
    """Freeze the DRAFT snapshot with server-computed Fair-Max."""
    try:
        snapshot = freeze_snapshot(asset_id, payload.model_dump(mode="json"))
        stored = snapshot.snapshot_payload
        return {
            "snapshot_id": str(snapshot.id),
            "snapshot_hash_sha256": snapshot.snapshot_hash_sha256,
            "snapshot_version": snapshot.snapshot_version,
            "fair_max_cents": stored["fair_max_cents"],
            "fair_max_min_cents": stored["fair_max_min_cents"],
            "fair_max_max_cents": stored["fair_max_max_cents"],
            "valuation_ruleset_version": stored["valuation_ruleset_version"],
            "attestation_applied": stored["attestation_applied"],
        }
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AssetNotDraftError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except AssetSnapshotNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (MissingValuationInputError, RulesetKeyError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except AttestationOutOfRangeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
