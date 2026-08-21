import json

from app.llm.base import BaseLLMClient, LLMMessage, LLMResponse


class MockLLMClient(BaseLLMClient):
    """Deterministic offline client for tests and development.

    Returns a valid structured JSON payload derived from the last
    user message, without any network access.
    """

    def __init__(self, response_content: str | None = None):
        self._response_content = response_content
        self.calls: list[list[LLMMessage]] = []

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        self.calls.append(messages)

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
        question = user_messages[-1].content if user_messages else ""
        payload = {
            "answer": f"Mock answer to: {question}",
            "reasoning_summary": "Mock reasoning: identified the question and produced a canned answer.",
            "suggested_next_steps": [
                "Inspect pods with GET /clusters/default/namespaces/{namespace}/pods",
                "Check events with GET /clusters/default/namespaces/{namespace}/events",
            ],
        }
        return json.dumps(payload)
