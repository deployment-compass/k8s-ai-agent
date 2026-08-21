import logging

from app.agent.loop import AgentLoop
from app.agent.tools import ToolRegistry
from app.config import settings
from app.kubernetes.client import KubernetesClient
from app.llm.base import BaseLLMClient
from app.llm.factory import create_llm_client
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

_llm_client: BaseLLMClient | None = None
_tool_registry: ToolRegistry | None = None


def get_llm_client() -> BaseLLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = create_llm_client(settings)
    return _llm_client


def set_llm_client(client: BaseLLMClient | None) -> None:
    """Replace the LLM client (used by tests)."""
    global _llm_client
    _llm_client = client


def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(KubernetesClient(), settings)
    return _tool_registry


def set_tool_registry(registry: ToolRegistry | None) -> None:
    """Replace the tool registry (used by tests)."""
    global _tool_registry
    _tool_registry = registry


async def handle_chat(request: ChatRequest) -> ChatResponse:
    logger.info("Chat request received: %r", request.message[:100])
    agent_loop = AgentLoop(get_llm_client(), get_tool_registry(), settings)
    result = await agent_loop.run(request.message)

    response = result.chat_response
    response.tools_used = result.tools_used
    return response
