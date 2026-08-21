from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ToolUsage(BaseModel):
    tool: str
    arguments: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    reasoning_summary: str
    suggested_next_steps: list[str] = Field(default_factory=list)
    tools_used: list[ToolUsage] = Field(default_factory=list)
