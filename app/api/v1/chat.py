from fastapi import APIRouter, HTTPException

from app.llm.base import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMParseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import handle_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await handle_chat(request)
    except LLMRateLimitError as exc:
        headers = (
            {"Retry-After": str(int(exc.retry_after_seconds))}
            if exc.retry_after_seconds is not None
            else None
        )
        raise HTTPException(
            status_code=429,
            detail="LLM rate limit exceeded. Please retry later.",
            headers=headers,
        ) from exc
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="LLM provider did not respond in time.",
        ) from exc
    except (LLMAuthError, LLMConnectionError, LLMProviderError, LLMParseError) as exc:
        raise _provider_error(exc) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM request failed.",
        ) from exc


def _provider_error(exc: LLMError) -> HTTPException:
    if isinstance(exc, LLMAuthError):
        return HTTPException(
            status_code=500,
            detail="LLM authentication failed. Check server configuration.",
        )
    if isinstance(exc, LLMParseError):
        return HTTPException(
            status_code=502,
            detail="LLM returned an invalid response.",
        )
    return HTTPException(
        status_code=502,
        detail="LLM provider is unavailable.",
    )
