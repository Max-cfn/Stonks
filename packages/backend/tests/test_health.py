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
async def test_health_returns_expected_payload(client):
    """Valide que GET /health retourne le payload exact attendu."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "status": "ok",
        "version": "0.1.0",
        "service": "stonks-backend",
    }
