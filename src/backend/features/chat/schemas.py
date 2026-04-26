from pydantic import BaseModel
from typing import Optional


class ChatMessageInput(BaseModel):
    role: str
    content: str


class ChatStartRequest(BaseModel):
    model: str
    messages: list[ChatMessageInput]
    context_tokens: int = 4096
    conversation_id: Optional[str] = None


class ChatStartResponse(BaseModel):
    request_id: str
    status: str
    conversation_id: Optional[str] = None


class ChatStopRequest(BaseModel):
    request_id: str
