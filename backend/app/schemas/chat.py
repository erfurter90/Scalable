from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    ai_available: bool
    reply: str | None
    data_used: dict | None = None  # the computed data handed to the LLM — shown for transparency
    error: str | None = None


class ChatStatusOut(BaseModel):
    configured: bool
