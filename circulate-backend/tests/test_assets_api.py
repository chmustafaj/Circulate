"""API tests for assets and verify endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from circulate_backend.api.main import app


@pytest.fixture
def sqlite_engine():
    """Placeholder for test signature; db is patched by conftest autouse fixture."""
    return None


@pytest.mark.asyncio
async def test_create_asset(sqlite_engine) -> None:
    """POST /assets creates DRAFT asset."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/assets")
    assert r.status_code == 200
    data = r.json()
    assert "asset_id" in data
    assert data["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_freeze_snapshot_success(sqlite_engine) -> None:
    """POST /assets/{id}/freeze creates snapshot."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_r = await client.post("/assets")
        asset_id = create_r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json={
                "fair_max_cents": 80000,
                "category": "jewelry",
                "serial_number": "SN-12345",
                "materials": "gold",
                "condition": "good",
                "photo_urls": ["https://example.com/watch-1.jpg"],
            },
        )
    assert freeze_r.status_code == 200
    data = freeze_r.json()
    assert "snapshot_id" in data
    assert "snapshot_hash_sha256" in data
    assert len(data["snapshot_hash_sha256"]) == 64


@pytest.mark.asyncio
async def test_freeze_snapshot_rejects_float(sqlite_engine) -> None:
    """Freeze rejects float in fair_max_cents."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_r = await client.post("/assets")
        asset_id = create_r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json={
                "fair_max_cents": 800.50,
                "serial_number": "SN-12345",
                "materials": "gold",
                "condition": "good",
                "photo_urls": ["https://example.com/watch-1.jpg"],
            },
        )
    assert freeze_r.status_code == 422


@pytest.mark.asyncio
async def test_verify_snapshot_with_payload(sqlite_engine) -> None:
    """POST /verify/snapshot with payload returns valid."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_r = await client.post("/assets")
        asset_id = create_r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json={
                "fair_max_cents": 80000,
                "category": "jewelry",
                "serial_number": "SN-12345",
                "materials": "gold",
                "condition": "good",
                "photo_urls": ["https://example.com/watch-1.jpg"],
            },
        )
        snapshot_id = freeze_r.json()["snapshot_id"]
        verify_r = await client.post(
            "/verify/snapshot",
            json={
                "snapshot_id": snapshot_id,
                "payload": {
                    "fair_max_cents": 80000,
                    "category": "jewelry",
                    "serial_number": "SN-12345",
                    "materials": "gold",
                    "condition": "good",
                    "photo_urls": ["https://example.com/watch-1.jpg"],
                },
            },
        )
    assert verify_r.status_code == 200
    assert verify_r.json()["valid"] is True


@pytest.mark.asyncio
async def test_verify_snapshot_invalid_payload(sqlite_engine) -> None:
    """POST /verify/snapshot with wrong payload returns valid=False."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_r = await client.post("/assets")
        asset_id = create_r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json={
                "fair_max_cents": 80000,
                "serial_number": "SN-12345",
                "materials": "gold",
                "condition": "good",
                "photo_urls": ["https://example.com/watch-1.jpg"],
            },
        )
        snapshot_id = freeze_r.json()["snapshot_id"]
        verify_r = await client.post(
            "/verify/snapshot",
            json={
                "snapshot_id": snapshot_id,
                "payload": {
                    "fair_max_cents": 90000,
                    "serial_number": "SN-12345",
                    "materials": "gold",
                    "condition": "good",
                    "photo_urls": ["https://example.com/watch-1.jpg"],
                },
            },
        )
    assert verify_r.status_code == 200
    assert verify_r.json()["valid"] is False


@pytest.mark.asyncio
async def test_verify_snapshot_without_payload(sqlite_engine) -> None:
    """POST /verify/snapshot without payload returns stored hash."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_r = await client.post("/assets")
        asset_id = create_r.json()["asset_id"]
        freeze_r = await client.post(
            f"/assets/{asset_id}/freeze",
            json={
                "fair_max_cents": 80000,
                "serial_number": "SN-12345",
                "materials": "gold",
                "condition": "good",
                "photo_urls": ["https://example.com/watch-1.jpg"],
            },
        )
        snapshot_id = freeze_r.json()["snapshot_id"]
        verify_r = await client.post(
            "/verify/snapshot",
            json={"snapshot_id": snapshot_id},
        )
    assert verify_r.status_code == 200
    data = verify_r.json()
    assert "stored_hash" in data
    assert "stored_payload" in data
    assert data["stored_payload"]["fair_max_cents"] == 80000
