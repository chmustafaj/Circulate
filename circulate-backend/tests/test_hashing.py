"""Tests for deterministic JSON canonicalization and SHA256 hashing."""

import pytest

from circulate_backend.domain.hashing import hash_snapshot_payload, reject_floats_in_payload


def test_hash_is_deterministic() -> None:
    """Same payload produces same hash regardless of key order."""
    payload1 = {
        "fair_max_cents": 80000,
        "category": "jewelry",
        "serial_number": "SN-12345",
        "materials": "gold",
        "condition": "good",
        "photo_urls": ["https://example.com/watch-1.jpg"],
    }
    payload2 = {
        "materials": "gold",
        "condition": "good",
        "photo_urls": ["https://example.com/watch-1.jpg"],
        "serial_number": "SN-12345",
        "fair_max_cents": 80000,
        "category": "jewelry",
    }
    assert hash_snapshot_payload(payload1) == hash_snapshot_payload(payload2)


def test_hash_rejects_floats() -> None:
    """Payloads containing floats raise ValueError."""
    with pytest.raises(ValueError, match="must not contain floating-point"):
        hash_snapshot_payload({"fair_max_cents": 80.5})


def test_hash_rejects_nested_floats() -> None:
    """Nested floats are rejected."""
    with pytest.raises(ValueError, match="must not contain floating-point"):
        hash_snapshot_payload({"fair_max_cents": 80000, "meta": {"weight": 1.5}})


def test_reject_floats_in_payload() -> None:
    """reject_floats_in_payload raises for floats."""
    reject_floats_in_payload({"x": 1})
    with pytest.raises(ValueError, match="must not contain floating-point"):
        reject_floats_in_payload({"x": 1.0})


def test_hash_output_format() -> None:
    """Hash is 64-char hex string."""
    h = hash_snapshot_payload(
        {
            "fair_max_cents": 80000,
            "serial_number": "SN-12345",
            "materials": "gold",
            "condition": "good",
            "photo_urls": ["https://example.com/watch-1.jpg"],
        }
    )
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
