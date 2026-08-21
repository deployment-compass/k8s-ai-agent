import json

import pytest

from app.agent.loop import set_prompted_mode
from app.config import settings
from app.llm.base import LLMParseError, LLMResponse
from app.llm.mock import MockLLMClient, ScriptedLLMClient
from app.schemas.chat import ChatRequest
from app.services import chat_service


@pytest.fixture(autouse=True)
def reset_singletons():
    chat_service.set_llm_client(None)
    chat_service.set_tool_registry(None)
    set_prompted_mode(False)
    yield
    chat_service.set_llm_client(None)
    chat_service.set_tool_registry(None)
    set_prompted_mode(False)


@pytest.fixture(autouse=True)
def native_tool_mode(monkeypatch):
    monkeypatch.setattr(settings, "llm_tool_mode", "native")


def _structured(answer="ok"):
    return json.dumps(
        {
            "answer": answer,
            "reasoning_summary": "why",
            "suggested_next_steps": ["step"],
        }
    )


@pytest.mark.asyncio
async def test_handle_chat_success():
    client = MockLLMClient()
    chat_service.set_llm_client(client)

    response = await chat_service.handle_chat(
        ChatRequest(message="What is CrashLoopBackOff?")
    )

    assert response.answer == "Mock answer to: What is CrashLoopBackOff?"
    assert response.tools_used == []
    assert len(client.calls) == 1
    messages, tools = client.calls[0]
    assert [m.role for m in messages] == ["system", "user"]
    assert isinstance(tools, list) and len(tools) == 21


@pytest.mark.asyncio
async def test_system_prompt_included():
    from app.agent.prompts import build_system_prompt

    client = MockLLMClient()
    chat_service.set_llm_client(client)

    await chat_service.handle_chat(ChatRequest(message="hi"))

    messages, _ = client.calls[0]
    first_message = messages[0]
    assert first_message.role == "system"
    assert "Kubernetes operations assistant" in first_message.content


@pytest.mark.asyncio
async def test_handle_chat_retries_once_on_invalid_json():
    bad = json.dumps({"reasoning_summary": "answer field is missing"})
    client = ScriptedLLMClient(
        [LLMResponse(content=bad), LLMResponse(content=_structured())]
    )
    chat_service.set_llm_client(client)

    response = await chat_service.handle_chat(ChatRequest(message="hi"))

    assert response.answer == "ok"
    assert len(client.calls) == 2
    retry_messages, retry_tools = client.calls[1]
    roles = [m.role for m in retry_messages]
    assert roles == ["system", "user", "user"]
    assert retry_tools is None


@pytest.mark.asyncio
async def test_handle_chat_raises_after_failed_retry():
    client = ScriptedLLMClient(
        [
            LLMResponse(content="this is not json at all"),
            LLMResponse(content="still not json"),
        ]
    )
    chat_service.set_llm_client(client)

    with pytest.raises(LLMParseError):
        await chat_service.handle_chat(ChatRequest(message="hi"))

    assert len(client.calls) == 2
