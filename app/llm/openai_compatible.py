import json
import logging
import time

import openai

from app.llm.base import (
    BaseLLMClient,
    LLMBadRequestError,
    LLMAuthError,
    LLMConnectionError,
    LLMMessage,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
    ToolCall,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleClient(BaseLLMClient):
    """Adapter for every OpenAI-compatible chat completions API.

    Covers OpenRouter, Groq, Google Gemini, Ollama and OpenAI itself
    by parameterizing base_url, api_key and model.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ):
        self.model = model
        self.temperature = temperature
        self._client = openai.AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or "not-set",
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        payload_messages = [self._serialize_message(m) for m in messages]
        kwargs: dict = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": tool} for tool in tools
            ]

        logger.debug(
            "LLM request: model=%s messages=%d tools=%d",
            self.model,
            len(payload_messages),
            len(kwargs.get("tools", ())),
        )
        started = time.perf_counter()
        try:
            completion = await self._client.chat.completions.create(**kwargs)
        except openai.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except openai.RateLimitError as exc:
            raise self._rate_limit_error(exc) from exc
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except openai.APIConnectionError as exc:
            raise LLMConnectionError(str(exc)) from exc
        except openai.InternalServerError as exc:
            raise LLMProviderError(str(exc)) from exc
        except openai.BadRequestError as exc:
            raise LLMBadRequestError(str(exc)) from exc

        response = self._to_response(completion)
        logger.debug(
            "LLM response: model=%s duration=%.2fs finish_reason=%s "
            "prompt_tokens=%s completion_tokens=%s tool_calls=%d",
            response.model,
            time.perf_counter() - started,
            response.finish_reason,
            response.prompt_tokens,
            response.completion_tokens,
            len(response.tool_calls),
        )
        return response

    @staticmethod
    def _serialize_message(message: LLMMessage) -> dict:
        payload: dict = {"role": message.role}
        if message.content is not None:
            payload["content"] = message.content
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in message.tool_calls
            ]
        if message.role == "tool":
            payload["tool_call_id"] = message.tool_call_id
            if message.name:
                payload["name"] = message.name
        return payload

    @staticmethod
    def _rate_limit_error(exc: openai.RateLimitError) -> LLMRateLimitError:
        retry_after: float | None = None
        if exc.response is not None:
            header = exc.response.headers.get("retry-after")
            if header is not None:
                try:
                    retry_after = float(header)
                except ValueError:
                    retry_after = None
        return LLMRateLimitError(str(exc), retry_after_seconds=retry_after)

    @staticmethod
    def _parse_tool_calls(raw_calls) -> tuple[ToolCall, ...]:
        calls = []
        for raw in raw_calls or []:
            try:
                arguments = json.loads(raw.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            calls.append(
                ToolCall(
                    id=raw.id or "",
                    name=raw.function.name or "",
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )
        return tuple(calls)

    def _to_response(self, completion) -> LLMResponse:
        choice = completion.choices[0] if completion.choices else None
        if choice is None:
            raise LLMProviderError("Model returned no choices.")

        content = choice.message.content
        tool_calls = self._parse_tool_calls(choice.message.tool_calls)
        if not content and not tool_calls:
            raise LLMProviderError("Model returned an empty response.")

        usage = getattr(completion, "usage", None)
        return LLMResponse(
            content=content,
            model=completion.model or self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
        )
