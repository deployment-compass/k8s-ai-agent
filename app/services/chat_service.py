from app.config import settings
from app.llm.base import BaseLLMClient, LLMParseError, LLMMessage, LLMResponse
from app.llm.factory import create_llm_client
from app.llm.parsing import validate_structured_output
from app.llm.prompts import SYSTEM_PROMPT
from app.schemas.chat import ChatRequest, ChatResponse

_client: BaseLLMClient | None = None


def get_llm_client() -> BaseLLMClient:
    global _client
    if _client is None:
        _client = create_llm_client(settings)
    return _client


def set_llm_client(client: BaseLLMClient) -> None:
    """Replace the client (used by tests)."""
    global _client
    _client = client


async def handle_chat(request: ChatRequest) -> ChatResponse:
    client = get_llm_client()
    messages = [
        LLMMessage.system(SYSTEM_PROMPT),
        LLMMessage.user(request.message),
    ]

    response = await client.complete(messages)
    try:
        return validate_structured_output(response.content, ChatResponse)
    except LLMParseError:
        pass

    retry_response = await _retry_with_feedback(client, messages, response.content)
    return validate_structured_output(retry_response.content, ChatResponse)


async def _retry_with_feedback(
    client: BaseLLMClient,
    messages: list[LLMMessage],
    invalid_content: str,
) -> LLMResponse:
    corrective = [
        *messages,
        LLMMessage(role="assistant", content=invalid_content),
        LLMMessage.user(
            "Your previous reply was not valid JSON matching the required schema. "
            "Respond again with ONLY the corrected JSON object, no other text."
        ),
    ]
    return await client.complete(corrective)
