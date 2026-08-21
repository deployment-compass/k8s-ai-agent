import pytest
from httpx import ASGITransport, AsyncClient

from app.llm.base import LLMAuthError, LLMRateLimitError, LLMTimeoutError
from app.llm.mock import MockLLMClient
from app.main import app
from app.services import chat_service


@pytest.fixture(autouse=True)
def mock_llm_client():
    client = MockLLMClient()
    chat_service.set_llm_client(client)
    yield client
    chat_service.set_llm_client(None)


@pytest.mark.asyncio
async def test_chat_endpoint_returns_structured_response(mock_llm_client):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Why is my backend unhealthy?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "Mock answer to: Why is my backend unhealthy?" in data["answer"]
    assert data["reasoning_summary"]
    assert isinstance(data["suggested_next_steps"], list)


@pytest.mark.asyncio
async def test_chat_endpoint_empty_message_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": ""},
        )

    assert response.status_code == 422


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


@pytest.mark.asyncio
async def test_chat_endpoint_maps_rate_limit_to_429():
    class RateLimitedClient(MockLLMClient):
        async def complete(self, messages):
            raise LLMRateLimitError("rate limited", retry_after_seconds=12)

    chat_service.set_llm_client(RateLimitedClient())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/chat", json={"message": "hi"})

    assert response.status_code == 429
    assert response.headers["retry-after"] == "12"


@pytest.mark.asyncio
async def test_chat_endpoint_maps_timeout_to_504():
    class TimeoutClient(MockLLMClient):
        async def complete(self, messages):
            raise LLMTimeoutError("timed out")

    chat_service.set_llm_client(TimeoutClient())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/chat", json={"message": "hi"})

    assert response.status_code == 504


@pytest.mark.asyncio
async def test_chat_endpoint_maps_auth_error_to_500():
    class AuthFailedClient(MockLLMClient):
        async def complete(self, messages):
            raise LLMAuthError("invalid key")

    chat_service.set_llm_client(AuthFailedClient())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/chat", json={"message": "hi"})

    assert response.status_code == 500
