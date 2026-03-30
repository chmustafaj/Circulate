"""Verification API router.

TODO: Add authentication for verification endpoints.
"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from circulate_backend.api.schemas.snapshot import SnapshotPayload
from circulate_backend.domain.verification_service import (
    SnapshotNotFoundError,
    get_snapshot_for_verification,
    verify_snapshot_payload,
)

router = APIRouter(prefix="/verify", tags=["verify"])


class VerifySnapshotRequest(BaseModel):
    snapshot_id: UUID
    payload: Optional[SnapshotPayload] = None


@router.post("/snapshot")
def verify_snapshot_endpoint(body: VerifySnapshotRequest) -> dict:
    """Verify snapshot against stored hash.

    - If payload provided: returns { valid: true/false }
    - If no payload: returns { stored_hash, stored_payload } for client-side verification
    """
    try:
        if body.payload is not None:
            valid = verify_snapshot_payload(body.snapshot_id, body.payload.model_dump(mode="json"))
            return {"valid": valid}
        stored_hash, stored_payload = get_snapshot_for_verification(body.snapshot_id)
        return {"stored_hash": stored_hash, "stored_payload": stored_payload}
    except SnapshotNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
