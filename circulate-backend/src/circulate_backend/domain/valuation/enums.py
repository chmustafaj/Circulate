"""Fixed enums for Fair-Max valuation inputs.

Every field that drives Fair-Max math uses one of these enums.
Free-form text is never used in the calculation.
"""

from __future__ import annotations

from enum import Enum


class ValuationMethod(str, Enum):
    metal = "metal"
    merchandise = "merchandise"


class Category(str, Enum):
    jewelry = "jewelry"
    electronics = "electronics"
    collectibles = "collectibles"
    other = "other"


class Subcategory(str, Enum):
    wristwatch = "wristwatch"
    bracelet = "bracelet"
    necklace = "necklace"
    ring = "ring"
    phone = "phone"
    laptop = "laptop"
    coin = "coin"
    other = "other"


class MetalProfile(str, Enum):
    gold_24k = "gold_24k"
    gold_22k = "gold_22k"
    gold_18k = "gold_18k"
    gold_14k = "gold_14k"
    gold_10k = "gold_10k"
    silver_925 = "silver_925"
    silver_999 = "silver_999"
    platinum_950 = "platinum_950"


class Condition(str, Enum):
    excellent = "excellent"
    good = "good"
    fair = "fair"
    poor = "poor"
