from pydantic import BaseModel


class ModelItem(BaseModel):
    name: str
    size: int | None = None
    quantization: str | None = None
    family: str | None = None


class StopModelRequest(BaseModel):
    model: str


class PullModelRequest(BaseModel):
    model: str
