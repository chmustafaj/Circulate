"""Strict schema for asset snapshot payloads."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from circulate_backend.api.schemas.common import Cents


class SnapshotPayload(BaseModel):
    """Strict schema for asset snapshot. Rejects floats and unknown fields."""

    model_config = ConfigDict(extra="forbid")

    fair_max_cents: Cents = Field(..., description="Fair-Max valuation in integer cents")
    category: Optional[str] = Field(None, max_length=64, description="Asset category e.g. jewelry")
    serial_number: Optional[str] = Field(
        None,
        max_length=128,
        description="Manufacturer or asset serial number when available.",
    )
    materials: str = Field(..., max_length=256, description="Material description")
    condition: str = Field(..., max_length=64, description="Condition e.g. excellent, good")
    photo_urls: list[HttpUrl] = Field(
        ...,
        min_length=1,
        description="Off-chain photo links included in the frozen asset passport.",
    )
