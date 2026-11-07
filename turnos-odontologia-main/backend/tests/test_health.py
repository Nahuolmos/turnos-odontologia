import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "turnos-odontologia-api"
        assert "database" in data
        assert "redis" in data


@pytest.mark.asyncio
async def test_health_check_structure():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["database"], str)
        assert isinstance(data["redis"], str)
        assert data["database"] in ("connected", "disconnected")
        assert data["redis"] in ("connected", "disconnected")
