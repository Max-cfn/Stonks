"""Tests for GET /health endpoint."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.app import create_app


@pytest_asyncio.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_version_is_string(client):
    resp = await client.get("/health")
    data = resp.json()
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0
