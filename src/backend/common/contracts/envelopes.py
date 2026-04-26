from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str
    correlation_id: str


class ApiEnvelope(BaseModel, Generic[T]):
    data: T


class StreamEvent(BaseModel):
    event_type: str
    request_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict
