"""Editor Chat — schemas."""
from typing import Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., min_length=1)


class FileContext(BaseModel):
    path: str
    content: str = ""
    language: str = ""
    selection: Optional[str] = None  # Selected text in editor


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    file_context: Optional[list[dict]] = None
    model: Optional[str] = None
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=16384)
    context_window: int = Field(default=8192, ge=1024, le=131072)
    workspace_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    model_used: str
    tokens_used: int
    latency_ms: int
    has_code_blocks: bool = False
