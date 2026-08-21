from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str
    reasoning_summary: str
    suggested_next_steps: list[str] = Field(default_factory=list)
