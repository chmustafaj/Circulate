"""Assets API router."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from circulate_backend.api.schemas.snapshot import SnapshotPayload
from circulate_backend.domain.asset_service import (
    AssetNotDraftError,
    AssetNotFoundError,
    create_asset,
    freeze_snapshot,
)

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("")
def create_asset_endpoint() -> dict:
    """Create a new asset in DRAFT status."""
    asset = create_asset()
    return {"asset_id": str(asset.id), "status": asset.status}


@router.post("/{asset_id}/freeze")
def freeze_snapshot_endpoint(asset_id: UUID, payload: SnapshotPayload) -> dict:
    """Freeze asset snapshot. One-time operation; asset must be DRAFT."""
    try:
        snapshot = freeze_snapshot(asset_id, payload.model_dump(mode="json"))
        return {
            "snapshot_id": str(snapshot.id),
            "snapshot_hash_sha256": snapshot.snapshot_hash_sha256,
            "snapshot_version": snapshot.snapshot_version,
        }
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AssetNotDraftError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
