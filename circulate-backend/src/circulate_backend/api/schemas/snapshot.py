"""Strict schemas for asset freeze requests and draft updates."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictInt, model_validator

from circulate_backend.api.schemas.common import Cents
from circulate_backend.domain.valuation.enums import (
    Category,
    Condition,
    MetalProfile,
    Subcategory,
    ValuationMethod,
)


class MetalInputs(BaseModel):
    """Structured inputs for the metal valuation path."""

    model_config = ConfigDict(extra="forbid")

    metal_profile: MetalProfile
    weight_mg: StrictInt = Field(..., gt=0, description="Gross weight in milligrams")
    stone_deduction_mg: StrictInt = Field(
        0,
        ge=0,
        description="Non-precious weight to subtract, in milligrams",
    )


class MerchandiseInputs(BaseModel):
    """Structured inputs for the merchandise valuation path.

    Fair-Max uses materials baseline (from category/subcategory) plus
    fabrication and skill time at ruleset rates (integer cents per minute).
    """

    model_config = ConfigDict(extra="forbid")

    subcategory: Subcategory
    fabrication_minutes: StrictInt = Field(
        ...,
        ge=0,
        le=1_000_000_000,
        description="Time invested in fabrication, minutes (integer).",
    )
    skill_minutes: StrictInt = Field(
        ...,
        ge=0,
        le=1_000_000_000,
        description="Time representing expertise / skill applied, minutes (integer).",
    )


class FreezeRequest(BaseModel):
    """Payload sent to POST /assets/{id}/freeze.

    Server computes fair_max_cents from these inputs.
    Rejects floats and unknown fields.
    """

    model_config = ConfigDict(extra="forbid")

    valuation_method: ValuationMethod
    category: Category
    condition: Condition

    metal: Optional[MetalInputs] = None
    merchandise: Optional[MerchandiseInputs] = None

    serial_number: Optional[str] = Field(
        None,
        max_length=128,
        description="Manufacturer or asset serial number when available.",
    )
    materials_description: Optional[str] = Field(
        None,
        max_length=256,
        description="Human-readable material description for display.",
    )
    photo_urls: list[HttpUrl] = Field(
        ...,
        min_length=1,
        description="Off-chain photo links included in the frozen asset passport.",
    )
    attested_fair_max_cents: Optional[Cents] = Field(
        None,
        description="Optional shop attestation; must fall within computed [min, max].",
    )

    @model_validator(mode="after")
    def _check_path_inputs(self) -> "FreezeRequest":
        if self.valuation_method == ValuationMethod.metal and self.metal is None:
            raise ValueError("metal inputs are required when valuation_method is 'metal'")
        if self.valuation_method == ValuationMethod.merchandise and self.merchandise is None:
            raise ValueError("merchandise inputs are required when valuation_method is 'merchandise'")
        if self.metal is not None and self.metal.weight_mg <= self.metal.stone_deduction_mg:
            raise ValueError("net metal weight must be positive after stone deduction")
        return self


class DraftUpdateRequest(BaseModel):
    """Partial update for asset draft. All fields optional."""

    model_config = ConfigDict(extra="forbid")

    valuation_method: Optional[ValuationMethod] = None
    category: Optional[Category] = None
    condition: Optional[Condition] = None
    metal: Optional[MetalInputs] = None
    merchandise: Optional[MerchandiseInputs] = None
    serial_number: Optional[str] = Field(None, max_length=128)
    materials_description: Optional[str] = Field(None, max_length=256)
    photo_urls: Optional[list[HttpUrl]] = None
    attested_fair_max_cents: Optional[Cents] = None
