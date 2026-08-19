from app.schemas.chat import ChatRequest, ChatResponse


async def handle_chat(request: ChatRequest) -> ChatResponse:
    response_text = (
        f"Echo: {request.message}\n\n"
        "This is a placeholder response. "
        "In future phases, this will be powered by an LLM with Kubernetes tools."
    )
    return ChatResponse(response=response_text)
