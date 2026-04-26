from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    command: str = Field(min_length=5, max_length=120)


class CommandControlRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=64)
