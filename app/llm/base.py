from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class LLMError(Exception):
    """Base exception for LLM failures."""


class LLMAuthError(LLMError):
    """Authentication with the provider failed (bad or missing API key)."""


class LLMRateLimitError(LLMError):
    """Provider rate limit hit. Optional retry_after_seconds when known."""

    def __init__(self, message: str, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LLMTimeoutError(LLMError):
    """The provider did not respond in time."""


class LLMConnectionError(LLMError):
    """Could not reach the provider at all."""


class LLMProviderError(LLMError):
    """The provider responded with an unexpected server-side failure."""


class LLMBadRequestError(LLMError):
    """The provider rejected the request payload (e.g. unsupported tools)."""


class LLMParseError(LLMError):
    """The model output could not be parsed into the expected structure."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None

    @classmethod
    def system(cls, content: str) -> "LLMMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "LLMMessage":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str | None = None, tool_calls: tuple[ToolCall, ...] = ()) -> "LLMMessage":
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool_result(cls, tool_call_id: str, name: str, content: str) -> "LLMMessage":
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)


@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    model: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    raw: dict = field(default_factory=dict)


class BaseLLMClient(ABC):
    """Boundary every LLM backend must implement.

    The rest of the application depends on this interface,
    never on a vendor SDK.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Send messages to the model and return its response.

        `tools` is a list of OpenAI-style tool definitions. When omitted,
        the request behaves as a plain completion.
        """
