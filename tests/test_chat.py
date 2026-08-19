import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_chat_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Why is my backend unhealthy?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "Why is my backend unhealthy?" in data["response"]


@pytest.mark.asyncio
async def test_chat_endpoint_empty_message():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": ""},
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data


@pytest.mark.asyncio
async def test_chat_endpoint_missing_message():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/chat",
            json={},
        )

    assert response.status_code == 422
