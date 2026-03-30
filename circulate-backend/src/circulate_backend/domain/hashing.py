"""Deterministic SHA256 hashing for asset snapshots.

Uses canonical JSON (RFC 8785) to ensure identical payloads produce identical hashes.
"""

from __future__ import annotations

import hashlib
from typing import Any

import canonicaljson


def _contains_float(obj: Any) -> bool:
    """Recursively check if object contains any float values."""
    if isinstance(obj, float):
        return True
    if isinstance(obj, dict):
        return any(_contains_float(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_float(v) for v in obj)
    return False


def reject_floats_in_payload(payload: dict[str, Any]) -> None:
    """Reject payloads containing floats. Raises ValueError if any float found."""
    if _contains_float(payload):
        raise ValueError("Payload must not contain floating-point values; use integer cents")


def hash_snapshot_payload(payload: dict[str, Any]) -> str:
    """Compute deterministic SHA256 hash of snapshot payload.

    Canonically formats JSON (sort keys, no whitespace) before hashing.
    Rejects payloads containing floats.

    Returns:
        64-character hex string (SHA256 digest).
    """
    reject_floats_in_payload(payload)
    canonical_bytes = canonicaljson.encode_canonical_json(payload)
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    return digest
