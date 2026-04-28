from pydantic import BaseModel, Field


class ModelItem(BaseModel):
    name: str
    size: int | None = None
    quantization: str | None = None
    family: str | None = None


class StopModelRequest(BaseModel):
    model: str


class PullModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=255)
