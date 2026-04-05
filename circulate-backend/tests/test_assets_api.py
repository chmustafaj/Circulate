"""API tests for assets, draft snapshot, freeze, and verify endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from circulate_backend.api.main import app


METAL_FREEZE_JSON = {
    "valuation_method": "metal",
    "category": "jewelry",
    "condition": "good",
    "metal": {
        "metal_profile": "gold_14k",
        "weight_mg": 24300,
    },
    "photo_urls": ["https://example.com/watch-1.jpg"],
}

MERCH_FREEZE_JSON = {
    "valuation_method": "merchandise",
    "category": "jewelry",
    "condition": "excellent",
    "merchandise": {
        "subcategory": "wristwatch",
        "fabrication_minutes": 100,
        "skill_minutes": 200,
    },
    "photo_urls": ["https://example.com/watch-1.jpg"],
}


@pytest.fixture
def sqlite_engine():
    """Placeholder; db is patched by conftest autouse fixture."""
    return None


# ── Create ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_asset(sqlite_engine) -> None:
    """POST /assets creates DRAFT asset and returns snapshot_id."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
    assert r.status_code == 200
    data = r.json()
    assert "asset_id" in data
    assert "snapshot_id" in data
    assert data["status"] == "DRAFT"
    assert data["snapshot_status"] == "DRAFT"


# ── GET ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_asset(sqlite_engine) -> None:
    """GET /assets/{id} returns asset and DRAFT snapshot payload."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        get_r = await client.get(f"/assets/{asset_id}")
    assert get_r.status_code == 200
    data = get_r.json()
    assert data["status"] == "DRAFT"
    assert data["snapshot_status"] == "DRAFT"
    assert data["snapshot_payload"] == {}


@pytest.mark.asyncio
async def test_get_asset_not_found(sqlite_engine) -> None:
    """GET /assets/{id} returns 404 for missing asset."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/assets/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ── PATCH (draft snapshot) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_draft_snapshot(sqlite_engine) -> None:
    """PATCH /assets/{id} merges into snapshot_payload."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        patch_r = await client.patch(
            f"/assets/{asset_id}",
            json={"category": "jewelry", "condition": "good"},
        )
    assert patch_r.status_code == 200
    data = patch_r.json()
    assert data["snapshot_status"] == "DRAFT"
    assert data["snapshot_payload"]["category"] == "jewelry"
    assert data["snapshot_payload"]["condition"] == "good"


@pytest.mark.asyncio
async def test_patch_rejects_frozen_asset(sqlite_engine) -> None:
    """PATCH /assets/{id} returns 409 after freeze."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        await client.post(f"/assets/{asset_id}/freeze", json=METAL_FREEZE_JSON)
        patch_r = await client.patch(
            f"/assets/{asset_id}",
            json={"condition": "poor"},
        )
    assert patch_r.status_code == 409


# ── Freeze — metal ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_freeze_metal_success(sqlite_engine) -> None:
    """POST /assets/{id}/freeze with metal inputs returns computed Fair-Max."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json=METAL_FREEZE_JSON,
        )
    assert freeze_r.status_code == 200
    data = freeze_r.json()
    assert "snapshot_id" in data
    assert len(data["snapshot_hash_sha256"]) == 64
    assert data["fair_max_cents"] == 109350
    assert data["fair_max_min_cents"] == 85050
    assert data["fair_max_max_cents"] == 139725
    assert data["valuation_ruleset_version"] == "2026-04-01"
    assert data["attestation_applied"] is False


# ── Freeze — product path (valuation_method merchandise) ───────────────


@pytest.mark.asyncio
async def test_freeze_product_path_success(sqlite_engine) -> None:
    """POST /assets/{id}/freeze with materials + time inputs returns computed Fair-Max."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json=MERCH_FREEZE_JSON,
        )
    assert freeze_r.status_code == 200
    data = freeze_r.json()
    assert data["fair_max_cents"] == 520000


# ── Freeze — validation ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_freeze_rejects_missing_metal_inputs(sqlite_engine) -> None:
    """Freeze rejects metal method without metal block."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json={
                "valuation_method": "metal",
                "category": "jewelry",
                "condition": "good",
                "photo_urls": ["https://example.com/pic.jpg"],
            },
        )
    assert freeze_r.status_code == 422


@pytest.mark.asyncio
async def test_freeze_rejects_float_weight(sqlite_engine) -> None:
    """Freeze rejects float in weight_mg (StrictInt)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json={
                "valuation_method": "metal",
                "category": "jewelry",
                "condition": "good",
                "metal": {"metal_profile": "gold_14k", "weight_mg": 24.3},
                "photo_urls": ["https://example.com/pic.jpg"],
            },
        )
    assert freeze_r.status_code == 422


@pytest.mark.asyncio
async def test_freeze_rejects_unknown_category(sqlite_engine) -> None:
    """Freeze rejects invalid category enum value."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json={
                "valuation_method": "metal",
                "category": "furniture",
                "condition": "good",
                "metal": {"metal_profile": "gold_14k", "weight_mg": 10000},
                "photo_urls": ["https://example.com/pic.jpg"],
            },
        )
    assert freeze_r.status_code == 422


@pytest.mark.asyncio
async def test_freeze_rejects_re_freeze(sqlite_engine) -> None:
    """Freeze returns 409 for already FROZEN asset."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        await client.post(f"/assets/{asset_id}/freeze", json=METAL_FREEZE_JSON)
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json=METAL_FREEZE_JSON,
        )
    assert freeze_r.status_code == 409


# ── Freeze — attestation ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_freeze_with_valid_attestation(sqlite_engine) -> None:
    """Attested value within range is accepted."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        payload = {**METAL_FREEZE_JSON, "attested_fair_max_cents": 100000}
        freeze_r = await client.post(f"/assets/{asset_id}/freeze", json=payload)
    assert freeze_r.status_code == 200
    data = freeze_r.json()
    assert data["fair_max_cents"] == 100000
    assert data["attestation_applied"] is True


@pytest.mark.asyncio
async def test_freeze_with_invalid_attestation(sqlite_engine) -> None:
    """Attested value outside range returns 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
        asset_id = r.json()["asset_id"]
        payload = {**METAL_FREEZE_JSON, "attested_fair_max_cents": 999999}
        freeze_r = await client.post(f"/assets/{asset_id}/freeze", json=payload)
    assert freeze_r.status_code == 422


# ── Verify ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_snapshot_round_trip(sqlite_engine) -> None:
    """Freeze then verify without payload returns stored hash and payload."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_r = await client.post("/assets")
        asset_id = create_r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json=METAL_FREEZE_JSON,
        )
        snapshot_id = freeze_r.json()["snapshot_id"]

        verify_r = await client.post(
            "/verify/snapshot",
            json={"snapshot_id": snapshot_id},
        )
    assert verify_r.status_code == 200
    data = verify_r.json()
    assert "stored_hash" in data
    assert data["stored_payload"]["fair_max_cents"] == 109350
