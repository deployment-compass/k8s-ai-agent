import json

from app.llm.base import BaseLLMClient, LLMMessage, LLMResponse


class MockLLMClient(BaseLLMClient):
    """Deterministic offline client for tests and development.

    Returns a valid structured JSON payload derived from the last
    user message, without any network access.
    """

    def __init__(self, response_content: str | None = None):
        self._response_content = response_content
        self.calls: list[tuple[list[LLMMessage], list[dict] | None]] = []

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        self.calls.append((messages, tools))

        if self._response_content is not None:
            content = self._response_content
        else:
            content = self._default_content(messages)

        return LLMResponse(
            content=content,
            model="mock",
            prompt_tokens=None,
            completion_tokens=None,
            finish_reason="stop",
        )

    def _default_content(self, messages: list[LLMMessage]) -> str:
        user_messages = [m for m in messages if m.role == "user"]
        question = next((m.content for m in reversed(user_messages) if m.content), "")
        payload = {
            "answer": f"Mock answer to: {question}",
            "reasoning_summary": "Mock reasoning: identified the question and produced a canned answer.",
            "suggested_next_steps": [
                "Inspect pods with GET /clusters/default/namespaces/{namespace}/pods",
                "Check events with GET /clusters/default/namespaces/{namespace}/events",
            ],
        }
        return json.dumps(payload)


class ScriptedLLMClient(BaseLLMClient):
    """Returns queued LLMResponses in order, recording every call.

    Lets tests drive multi-turn tool-calling conversations deterministically.
    """

    def __init__(self, responses: list[LLMResponse]):
        self._responses = iter(responses)
        self.calls: list[tuple[list[LLMMessage], list[dict] | None]] = []

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        self.calls.append((messages, tools))
        try:
            return next(self._responses)
        except StopIteration as exc:
            raise AssertionError("ScriptedLLMClient ran out of responses.") from exc
