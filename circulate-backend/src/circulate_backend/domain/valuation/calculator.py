"""Fair-Max baseline calculator.

Pure function — no DB, no side effects, integer-only math.
All division uses floor (//) with a single documented rule.

Merchandise path: baseline = f(materials) + rate_fab * fabrication_minutes + rate_skill * skill_minutes,
then condition adjustment and policy floor/cap on the pre-condition total.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from circulate_backend.domain.valuation.enums import (
    Category,
    Condition,
    MetalProfile,
    Subcategory,
    ValuationMethod,
)


def _enum_val(v: Any) -> str:
    """Extract the string value from an enum or pass through a plain string."""
    return v.value if isinstance(v, Enum) else v


class AttestationOutOfRangeError(Exception):
    """Raised when the shop's attested value falls outside [min, max]."""

    pass


class MissingValuationInputError(Exception):
    """Raised when required inputs for the chosen valuation method are absent."""

    pass


class RulesetKeyError(Exception):
    """Raised when a required key is missing from the ruleset."""

    pass


@dataclass(frozen=True)
class FairMaxResult:
    fair_max_cents: int
    baseline_cents: int
    min_cents: int
    max_cents: int
    ruleset_version: str
    attestation_applied: bool


def _lookup(ruleset: dict[str, Any], *keys: str) -> Any:
    """Walk nested keys in the ruleset, raising RulesetKeyError on miss."""
    node = ruleset
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            raise RulesetKeyError(f"Ruleset missing key path: {'.'.join(keys)}")
        node = node[key]
    return node


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))


def _compute_metal(
    metal_profile: MetalProfile,
    weight_mg: int,
    stone_deduction_mg: int,
    condition: Condition,
    ruleset: dict[str, Any],
) -> tuple[int, int, int]:
    """Return (baseline_cents, min_cents, max_cents) for the metal path."""
    cents_per_mg: int = _lookup(ruleset, "metal_cents_per_mg", _enum_val(metal_profile))
    condition_bps: int = _lookup(ruleset, "condition_bps", _enum_val(condition))
    cap_bps: int = _lookup(ruleset, "policy", "metal_cap_bps")
    floor_bps: int = _lookup(ruleset, "policy", "metal_floor_bps")

    net_mg = weight_mg - stone_deduction_mg
    if net_mg <= 0:
        raise MissingValuationInputError("Net metal weight must be positive after stone deduction")

    raw_cents = net_mg * cents_per_mg
    baseline_cents = raw_cents * condition_bps // 10000
    min_cents = raw_cents * floor_bps // 10000
    max_cents = raw_cents * cap_bps // 10000

    return baseline_cents, min_cents, max_cents


def _compute_merchandise(
    category: Category,
    subcategory: Subcategory,
    condition: Condition,
    fabrication_minutes: int,
    skill_minutes: int,
    ruleset: dict[str, Any],
) -> tuple[int, int, int]:
    """Fair-Max for the non-metal path: materials anchor + time at policy rates.

    pre_condition_cents = materials_baseline + fab_min * rate_fab + skill_min * rate_skill
    baseline_cents = pre_condition_cents * condition_bps // 10000
    min/max use policy product_valuation_floor_bps / product_valuation_cap_bps on pre_condition_cents.
    """
    anchor_key = f"{_enum_val(category)}.{_enum_val(subcategory)}"
    materials_baseline: int = _lookup(ruleset, "category_anchors_cents", anchor_key)
    condition_bps: int = _lookup(ruleset, "condition_bps", _enum_val(condition))
    rate_fab: int = _lookup(ruleset, "time_rates", "fabrication_cents_per_minute")
    rate_skill: int = _lookup(ruleset, "time_rates", "skill_cents_per_minute")
    cap_bps: int = _lookup(ruleset, "policy", "product_valuation_cap_bps")
    floor_bps: int = _lookup(ruleset, "policy", "product_valuation_floor_bps")

    if fabrication_minutes < 0 or skill_minutes < 0:
        raise MissingValuationInputError("fabrication_minutes and skill_minutes must be non-negative")

    fab_cents = fabrication_minutes * rate_fab
    skill_cents = skill_minutes * rate_skill
    pre_condition_cents = materials_baseline + fab_cents + skill_cents

    baseline_cents = pre_condition_cents * condition_bps // 10000
    min_cents = pre_condition_cents * floor_bps // 10000
    max_cents = pre_condition_cents * cap_bps // 10000

    return baseline_cents, min_cents, max_cents


def compute_fair_max(
    *,
    valuation_method: ValuationMethod,
    category: Category,
    condition: Condition,
    metal_profile: MetalProfile | None = None,
    weight_mg: int | None = None,
    stone_deduction_mg: int = 0,
    subcategory: Subcategory | None = None,
    fabrication_minutes: int | None = None,
    skill_minutes: int | None = None,
    attested_fair_max_cents: int | None = None,
    ruleset: dict[str, Any],
) -> FairMaxResult:
    """Compute Fair-Max valuation from structured inputs + versioned ruleset.

    All arithmetic is integer-only with floor division (//).
    """
    if valuation_method == ValuationMethod.metal:
        if metal_profile is None or weight_mg is None:
            raise MissingValuationInputError("metal_profile and weight_mg are required for metal valuation")
        baseline_cents, min_cents, max_cents = _compute_metal(
            metal_profile=metal_profile,
            weight_mg=weight_mg,
            stone_deduction_mg=stone_deduction_mg,
            condition=condition,
            ruleset=ruleset,
        )
    elif valuation_method == ValuationMethod.merchandise:
        if subcategory is None or fabrication_minutes is None or skill_minutes is None:
            raise MissingValuationInputError(
                "subcategory, fabrication_minutes, and skill_minutes are required for merchandise valuation"
            )
        baseline_cents, min_cents, max_cents = _compute_merchandise(
            category=category,
            subcategory=subcategory,
            condition=condition,
            fabrication_minutes=fabrication_minutes,
            skill_minutes=skill_minutes,
            ruleset=ruleset,
        )
    else:
        raise MissingValuationInputError(f"Unknown valuation method: {valuation_method}")

    fair_max_cents = _clamp(baseline_cents, min_cents, max_cents)
    attestation_applied = False

    if attested_fair_max_cents is not None:
        if attested_fair_max_cents < min_cents or attested_fair_max_cents > max_cents:
            raise AttestationOutOfRangeError(
                f"Attested value {attested_fair_max_cents} is outside allowed range "
                f"[{min_cents}, {max_cents}]"
            )
        fair_max_cents = attested_fair_max_cents
        attestation_applied = True

    return FairMaxResult(
        fair_max_cents=fair_max_cents,
        baseline_cents=baseline_cents,
        min_cents=min_cents,
        max_cents=max_cents,
        ruleset_version=ruleset["version"],
        attestation_applied=attestation_applied,
    )
