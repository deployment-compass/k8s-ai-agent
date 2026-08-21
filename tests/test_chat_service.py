import json

import pytest

from app.llm.base import LLMParseError, LLMMessage, LLMResponse
from app.llm.mock import MockLLMClient
from app.schemas.chat import ChatRequest
from app.services import chat_service


class ScriptedClient(MockLLMClient):
    """Returns queued responses in order, recording every call."""

    def __init__(self, responses: list[str]):
        super().__init__()
        self._responses = iter(responses)

    async def complete(self, messages):
        self.calls.append(messages)
        return LLMResponse(content=next(self._responses), model="scripted")


@pytest.fixture(autouse=True)
def reset_client():
    chat_service.set_llm_client(None)
    yield
    chat_service.set_llm_client(None)


@pytest.mark.asyncio
async def test_handle_chat_success():
    client = MockLLMClient()
    chat_service.set_llm_client(client)

    response = await chat_service.handle_chat(ChatRequest(message="What is CrashLoopBackOff?"))

    assert response.answer == "Mock answer to: What is CrashLoopBackOff?"
    assert len(client.calls) == 1
    roles = [m.role for m in client.calls[0]]
    assert roles == ["system", "user"]


@pytest.mark.asyncio
async def test_handle_chat_retries_once_on_invalid_json():
    bad = json.dumps({"reasoning_summary": "answer field is missing"})
    good = json.dumps(
        {
            "answer": "ok",
            "reasoning_summary": "why",
            "suggested_next_steps": ["step"],
        }
    )
    client = ScriptedClient([bad, good])
    chat_service.set_llm_client(client)

    response = await chat_service.handle_chat(ChatRequest(message="hi"))

    assert response.answer == "ok"
    assert response.suggested_next_steps == ["step"]
    assert len(client.calls) == 2
    retry_roles = [m.role for m in client.calls[1]]
    assert retry_roles == ["system", "user", "assistant", "user"]


@pytest.mark.asyncio
async def test_handle_chat_raises_after_failed_retry():
    client = ScriptedClient(["this is not json at all", "still not json"])
    chat_service.set_llm_client(client)

    with pytest.raises(LLMParseError):
        await chat_service.handle_chat(ChatRequest(message="hi"))

    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_system_prompt_included():
    from app.llm.prompts import SYSTEM_PROMPT

    client = MockLLMClient()
    chat_service.set_llm_client(client)

    await chat_service.handle_chat(ChatRequest(message="hi"))

    first_message: LLMMessage = client.calls[0][0]
    assert first_message.role == "system"
    assert "Kubernetes operations assistant" in first_message.content
