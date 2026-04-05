"""Unit tests for Fair-Max calculator — pure integer math, no DB."""

from __future__ import annotations

import pytest

from circulate_backend.domain.valuation.calculator import (
    AttestationOutOfRangeError,
    MissingValuationInputError,
    RulesetKeyError,
    compute_fair_max,
)
from circulate_backend.domain.valuation.enums import (
    Category,
    Condition,
    MetalProfile,
    Subcategory,
    ValuationMethod,
)
from circulate_backend.domain.valuation.ruleset_loader import load_ruleset


@pytest.fixture()
def ruleset():
    return load_ruleset("2026-04-01")


# ── Metal path ──────────────────────────────────────────────────────────


class TestMetalPath:
    def test_basic_gold_14k(self, ruleset):
        result = compute_fair_max(
            valuation_method=ValuationMethod.metal,
            category=Category.jewelry,
            condition=Condition.good,
            metal_profile=MetalProfile.gold_14k,
            weight_mg=24300,
            ruleset=ruleset,
        )
        # raw = 24300 * 5 = 121500
        # baseline = 121500 * 9000 // 10000 = 109350
        # min = 121500 * 7000 // 10000 = 85050
        # max = 121500 * 11500 // 10000 = 139725
        assert result.baseline_cents == 109350
        assert result.min_cents == 85050
        assert result.max_cents == 139725
        assert result.fair_max_cents == 109350
        assert result.attestation_applied is False
        assert result.ruleset_version == "2026-04-01"

    def test_stone_deduction(self, ruleset):
        result = compute_fair_max(
            valuation_method=ValuationMethod.metal,
            category=Category.jewelry,
            condition=Condition.excellent,
            metal_profile=MetalProfile.gold_18k,
            weight_mg=10000,
            stone_deduction_mg=2000,
            ruleset=ruleset,
        )
        # net = 8000, raw = 8000 * 6 = 48000
        # baseline = 48000 * 10000 // 10000 = 48000
        # min = 48000 * 7000 // 10000 = 33600
        # max = 48000 * 11500 // 10000 = 55200
        assert result.baseline_cents == 48000
        assert result.fair_max_cents == 48000

    def test_poor_condition_clamps_to_floor(self, ruleset):
        result = compute_fair_max(
            valuation_method=ValuationMethod.metal,
            category=Category.jewelry,
            condition=Condition.poor,
            metal_profile=MetalProfile.gold_14k,
            weight_mg=10000,
            ruleset=ruleset,
        )
        # raw = 50000, baseline = 50000 * 5000 // 10000 = 25000
        # min = 50000 * 7000 // 10000 = 35000
        # baseline < min → clamped to 35000
        assert result.baseline_cents == 25000
        assert result.fair_max_cents == 35000

    def test_missing_metal_profile_raises(self, ruleset):
        with pytest.raises(MissingValuationInputError):
            compute_fair_max(
                valuation_method=ValuationMethod.metal,
                category=Category.jewelry,
                condition=Condition.good,
                weight_mg=10000,
                ruleset=ruleset,
            )

    def test_missing_weight_raises(self, ruleset):
        with pytest.raises(MissingValuationInputError):
            compute_fair_max(
                valuation_method=ValuationMethod.metal,
                category=Category.jewelry,
                condition=Condition.good,
                metal_profile=MetalProfile.gold_14k,
                ruleset=ruleset,
            )

    def test_zero_net_weight_raises(self, ruleset):
        with pytest.raises(MissingValuationInputError, match="positive"):
            compute_fair_max(
                valuation_method=ValuationMethod.metal,
                category=Category.jewelry,
                condition=Condition.good,
                metal_profile=MetalProfile.gold_14k,
                weight_mg=5000,
                stone_deduction_mg=5000,
                ruleset=ruleset,
            )


# ── Merchandise path ────────────────────────────────────────────────────


class TestMerchandisePath:
    def test_wristwatch_materials_plus_time(self, ruleset):
        """pre = anchor + fab_min*50 + skill_min*75; then condition; floor/cap on pre."""
        result = compute_fair_max(
            valuation_method=ValuationMethod.merchandise,
            category=Category.jewelry,
            condition=Condition.excellent,
            subcategory=Subcategory.wristwatch,
            fabrication_minutes=100,
            skill_minutes=200,
            ruleset=ruleset,
        )
        # materials 500000 + 100*50 + 200*75 = 520000
        # baseline = 520000 * 10000 // 10000 = 520000
        # min = 520000 * 5000 // 10000 = 260000
        # max = 520000 * 13000 // 10000 = 676000
        assert result.baseline_cents == 520000
        assert result.min_cents == 260000
        assert result.max_cents == 676000
        assert result.fair_max_cents == 520000

    def test_phone_zero_time(self, ruleset):
        result = compute_fair_max(
            valuation_method=ValuationMethod.merchandise,
            category=Category.electronics,
            condition=Condition.good,
            subcategory=Subcategory.phone,
            fabrication_minutes=0,
            skill_minutes=0,
            ruleset=ruleset,
        )
        # pre = 80000, after_condition = 80000 * 9000 // 10000 = 72000
        # min = 80000 * 5000 // 10000 = 40000
        # max = 80000 * 13000 // 10000 = 104000
        assert result.baseline_cents == 72000
        assert result.fair_max_cents == 72000

    def test_missing_subcategory_raises(self, ruleset):
        with pytest.raises(MissingValuationInputError):
            compute_fair_max(
                valuation_method=ValuationMethod.merchandise,
                category=Category.jewelry,
                condition=Condition.good,
                fabrication_minutes=0,
                skill_minutes=0,
                ruleset=ruleset,
            )

    def test_missing_fabrication_minutes_raises(self, ruleset):
        with pytest.raises(MissingValuationInputError):
            compute_fair_max(
                valuation_method=ValuationMethod.merchandise,
                category=Category.jewelry,
                condition=Condition.good,
                subcategory=Subcategory.wristwatch,
                skill_minutes=0,
                ruleset=ruleset,
            )

    def test_missing_skill_minutes_raises(self, ruleset):
        with pytest.raises(MissingValuationInputError):
            compute_fair_max(
                valuation_method=ValuationMethod.merchandise,
                category=Category.jewelry,
                condition=Condition.good,
                subcategory=Subcategory.wristwatch,
                fabrication_minutes=0,
                ruleset=ruleset,
            )


# ── Attestation ─────────────────────────────────────────────────────────


class TestAttestation:
    def test_attested_within_range_accepted(self, ruleset):
        result = compute_fair_max(
            valuation_method=ValuationMethod.metal,
            category=Category.jewelry,
            condition=Condition.good,
            metal_profile=MetalProfile.gold_14k,
            weight_mg=24300,
            attested_fair_max_cents=100000,
            ruleset=ruleset,
        )
        # min=85050, max=139725 → 100000 is within range
        assert result.fair_max_cents == 100000
        assert result.attestation_applied is True

    def test_attested_at_boundary_accepted(self, ruleset):
        result = compute_fair_max(
            valuation_method=ValuationMethod.metal,
            category=Category.jewelry,
            condition=Condition.good,
            metal_profile=MetalProfile.gold_14k,
            weight_mg=24300,
            attested_fair_max_cents=85050,
            ruleset=ruleset,
        )
        assert result.fair_max_cents == 85050
        assert result.attestation_applied is True

    def test_attested_below_range_rejected(self, ruleset):
        with pytest.raises(AttestationOutOfRangeError, match="outside allowed range"):
            compute_fair_max(
                valuation_method=ValuationMethod.metal,
                category=Category.jewelry,
                condition=Condition.good,
                metal_profile=MetalProfile.gold_14k,
                weight_mg=24300,
                attested_fair_max_cents=50000,
                ruleset=ruleset,
            )

    def test_attested_above_range_rejected(self, ruleset):
        with pytest.raises(AttestationOutOfRangeError, match="outside allowed range"):
            compute_fair_max(
                valuation_method=ValuationMethod.metal,
                category=Category.jewelry,
                condition=Condition.good,
                metal_profile=MetalProfile.gold_14k,
                weight_mg=24300,
                attested_fair_max_cents=999999,
                ruleset=ruleset,
            )


# ── Determinism ─────────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_inputs_same_output(self, ruleset):
        kwargs = dict(
            valuation_method=ValuationMethod.metal,
            category=Category.jewelry,
            condition=Condition.good,
            metal_profile=MetalProfile.gold_14k,
            weight_mg=24300,
            ruleset=ruleset,
        )
        a = compute_fair_max(**kwargs)
        b = compute_fair_max(**kwargs)
        assert a == b

    def test_no_floats_in_result(self, ruleset):
        result = compute_fair_max(
            valuation_method=ValuationMethod.metal,
            category=Category.jewelry,
            condition=Condition.good,
            metal_profile=MetalProfile.gold_14k,
            weight_mg=24300,
            ruleset=ruleset,
        )
        assert isinstance(result.fair_max_cents, int)
        assert isinstance(result.baseline_cents, int)
        assert isinstance(result.min_cents, int)
        assert isinstance(result.max_cents, int)


# ── Ruleset errors ──────────────────────────────────────────────────────


class TestRulesetErrors:
    def test_missing_metal_key_raises(self):
        bad_ruleset = {"version": "test", "metal_cents_per_mg": {}, "condition_bps": {}, "policy": {}}
        with pytest.raises(RulesetKeyError):
            compute_fair_max(
                valuation_method=ValuationMethod.metal,
                category=Category.jewelry,
                condition=Condition.good,
                metal_profile=MetalProfile.gold_14k,
                weight_mg=10000,
                ruleset=bad_ruleset,
            )
