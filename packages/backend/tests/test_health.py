"""Tests for health check endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from stonks_backend.app import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "stonks-backend"
    assert "version" in data


@pytest.mark.asyncio
async def test_ready_returns_status(client: AsyncClient) -> None:
    """Ready probe returns status — may be 'not_ready' if no DB/Vault."""
    resp = await client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ready", "not_ready")
    assert "checks" in data
    assert "database" in data["checks"]
    assert "vault" in data["checks"]
