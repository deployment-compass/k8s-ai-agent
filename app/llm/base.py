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


class LLMParseError(LLMError):
    """The model output could not be parsed into the expected structure."""


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str

    @classmethod
    def system(cls, content: str) -> "LLMMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "LLMMessage":
        return cls(role="user", content=content)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None
    raw: dict = field(default_factory=dict)


class BaseLLMClient(ABC):
    """Boundary every LLM backend must implement.

    The rest of the application depends on this interface,
    never on a vendor SDK.
    """

    @abstractmethod
    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        """Send messages to the model and return its raw text response."""
