import json

import pytest

from app.agent.loop import AgentLoop, set_prompted_mode
from app.config import Settings, settings
from app.llm.base import LLMBadRequestError, LLMParseError, LLMResponse, ToolCall
from app.llm.mock import ScriptedLLMClient
from app.schemas.chat import ChatRequest
from app.services import chat_service


class FakeRegistry:
    def __init__(self):
        self.executed = []

    def definitions(self):
        return [
            {"name": "get_pods", "description": "list pods", "parameters": {}},
            {"name": "get_events", "description": "list events", "parameters": {}},
        ]

    def known_tools(self):
        return "get_events, get_pods"

    async def execute(self, name, arguments):
        self.executed.append((name, arguments))
        if name not in ("get_pods", "get_events"):
            return json.dumps(
                {"error": f"Unknown tool '{name}'. Valid tools: {self.known_tools()}"}
            )
        return json.dumps({"items": [], "count": 0})


@pytest.fixture(autouse=True)
def reset_singletons():
    chat_service.set_llm_client(None)
    chat_service.set_tool_registry(None)
    set_prompted_mode(False)
    yield
    chat_service.set_llm_client(None)
    chat_service.set_tool_registry(None)
    set_prompted_mode(False)


def _structured(answer="diagnosis"):
    return json.dumps(
        {
            "answer": answer,
            "reasoning_summary": "path",
            "suggested_next_steps": [],
        }
    )


def _tool_call(name="get_pods", arguments=None, call_id="call-1"):
    return ToolCall(id=call_id, name=name, arguments=arguments or {"namespace": "backend"})


async def _run(llm_client, monkeypatch=None):
    registry = FakeRegistry()
    chat_service.set_llm_client(llm_client)
    chat_service.set_tool_registry(registry)
    result = await chat_service.handle_chat(ChatRequest(message="why is backend broken?"))
    return result, registry


@pytest.mark.asyncio
async def test_native_single_tool_round_trip():
    client = ScriptedLLMClient(
        [
            LLMResponse(content=None, tool_calls=(_tool_call(),)),
            LLMResponse(content=_structured()),
        ]
    )

    result, registry = await _run(client)

    assert result.answer == "diagnosis"
    assert registry.executed == [("get_pods", {"namespace": "backend"})]
    assert len(result.tools_used) == 1
    assert result.tools_used[0].tool == "get_pods"

    second_messages, _ = client.calls[1]
    roles = [m.role for m in second_messages]
    assert roles == ["system", "user", "assistant", "tool"]


@pytest.mark.asyncio
async def test_native_multi_tool_sequence():
    client = ScriptedLLMClient(
        [
            LLMResponse(content=None, tool_calls=(_tool_call("get_deployments"),)),
            LLMResponse(
                content=None,
                tool_calls=(
                    _tool_call("get_pods", {"namespace": "backend"}, "call-2"),
                    _tool_call("get_events", {"namespace": "backend"}, "call-3"),
                ),
            ),
            LLMResponse(content=_structured()),
        ]
    )

    result, registry = await _run(client)

    assert [t.tool for t in result.tools_used] == [
        "get_deployments",
        "get_pods",
        "get_events",
    ]
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_unknown_tool_error_fed_back_not_raised():
    client = ScriptedLLMClient(
        [
            LLMResponse(content=None, tool_calls=(_tool_call("delete_everything"),)),
            LLMResponse(content=_structured()),
        ]
    )

    result, registry = await _run(client)

    assert result.answer == "diagnosis"
    assert registry.executed[0][0] == "delete_everything"
    tool_message = client.calls[1][0][-1]
    assert "Unknown tool" in tool_message.content


@pytest.mark.asyncio
async def test_max_iterations_forces_final_answer():
    responses = [
        LLMResponse(content=None, tool_calls=(_tool_call(call_id=f"c{i}"),))
        for i in range(settings.agent_max_tool_iterations)
    ]
    responses.append(LLMResponse(content=_structured("forced answer")))
    client = ScriptedLLMClient(responses)

    result, _ = await _run(client)

    assert result.answer == "forced answer"
    assert len(result.tools_used) == settings.agent_max_tool_iterations


@pytest.mark.asyncio
async def test_auto_downgrade_on_unparseable_first_response(monkeypatch):
    monkeypatch.setattr(settings, "llm_tool_mode", "auto")
    prompted_call = json.dumps(
        {"action": "tool_call", "tool": "get_pods", "arguments": {"namespace": "ns1"}}
    )
    prompted_final = json.dumps(
        {
            "action": "final_answer",
            "answer": "done",
            "reasoning_summary": "r",
            "suggested_next_steps": [],
        }
    )
    client = ScriptedLLMClient(
        [
            LLMResponse(content="I will check the pods for you."),  # garbage in native mode
            LLMResponse(content=prompted_call),  # prompted mode now
            LLMResponse(content=prompted_final),
        ]
    )

    result, registry = await _run(client)

    assert result.answer == "done"
    assert registry.executed == [("get_pods", {"namespace": "ns1"})]
    assert set_prompted_mode is not None
    from app.agent.loop import _prompted_mode_active

    assert _prompted_mode_active is True


@pytest.mark.asyncio
async def test_bad_request_downgrades_to_prompted(monkeypatch):
    monkeypatch.setattr(settings, "llm_tool_mode", "auto")

    class RejectsTools(ScriptedLLMClient):
        async def complete(self, messages, tools=None):
            if tools:
                raise LLMBadRequestError("tools not supported")
            return await super().complete(messages, tools=None)

    prompted_final = json.dumps(
        {
            "action": "final_answer",
            "answer": "prompted works",
            "reasoning_summary": "r",
            "suggested_next_steps": [],
        }
    )
    client = RejectsTools([LLMResponse(content=prompted_final)])

    result, _ = await _run(client)

    assert result.answer == "prompted works"


@pytest.mark.asyncio
async def test_prompted_mode_explicit_setting(monkeypatch):
    monkeypatch.setattr(settings, "llm_tool_mode", "prompted")
    prompted_call = json.dumps(
        {"action": "tool_call", "tool": "get_pods", "arguments": {}}
    )
    client = ScriptedLLMClient(
        [LLMResponse(content=prompted_call), LLMResponse(content=_structured())]
    )

    result, registry = await _run(client)

    assert registry.executed == [("get_pods", {})]
    assert result.answer == "diagnosis"
    _, tools_first_call = client.calls[0]
    assert tools_first_call is None


@pytest.mark.asyncio
async def test_prompted_final_answer_without_action_wrapper():
    monkeypatch = None
    set_prompted_mode(True)
    plain_structured = _structured("no wrapper")
    client = ScriptedLLMClient([LLMResponse(content=plain_structured)])

    result, _ = await _run(client)

    assert result.answer == "no wrapper"
