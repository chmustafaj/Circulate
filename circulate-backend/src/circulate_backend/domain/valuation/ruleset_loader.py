"""Load and cache versioned JSON rulesets for Fair-Max valuation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RULESETS_DIR = Path(__file__).parent / "rulesets"

CURRENT_RULESET_VERSION = "2026-04-01"


@lru_cache(maxsize=8)
def load_ruleset(version: str | None = None) -> dict[str, Any]:
    """Load a ruleset JSON by version string.

    Raises FileNotFoundError if the version file does not exist.
    """
    version = version or CURRENT_RULESET_VERSION
    filename = version.replace("-", "_") + ".json"
    path = RULESETS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Ruleset {version} not found at {path}")
    with open(path) as f:
        return json.load(f)
