import openai

from app.llm.base import (
    BaseLLMClient,
    LLMAuthError,
    LLMConnectionError,
    LLMMessage,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
)


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

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        payload = [{"role": m.role, "content": m.content} for m in messages]
        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=payload,
                temperature=self.temperature,
            )
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

        return self._to_response(completion)

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

    def _to_response(self, completion) -> LLMResponse:
        choice = completion.choices[0] if completion.choices else None
        content = choice.message.content if choice else None
        if not content:
            raise LLMProviderError("Model returned an empty response.")

        usage = getattr(completion, "usage", None)
        return LLMResponse(
            content=content,
            model=completion.model or self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            finish_reason=choice.finish_reason,
        )
