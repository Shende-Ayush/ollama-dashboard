"""AI Coding — Request/Response schemas."""
from typing import Optional
from pydantic import BaseModel, Field

class CompletionRequest(BaseModel):
    prefix: str = Field(..., description="Code before cursor")
    suffix: str = Field(default="", description="Code after cursor")
    language: str = Field(..., description="Programming language")
    file_path: Optional[str] = None
    workspace_id: Optional[str] = None
    model: Optional[str] = Field(default=None, description="Override model selection")
    max_tokens: int = Field(default=256, ge=1, le=2048)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    stop: list[str] = Field(default_factory=list)

class CompletionResponse(BaseModel):
    completion: str
    model_used: str
    tokens_generated: int
    latency_ms: int
    cache_hit: bool = False
    finish_reason: str = "stop"  # stop, length, error

class CodeActionRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50000)
    action: str = Field(..., description="Action: explain, refactor, optimize, fix, add_docs, add_tests")
    language: str = Field(default="python")
    context: Optional[str] = Field(default=None, description="Additional context")
    model: Optional[str] = None

class CodeActionResponse(BaseModel):
    result: str
    action: str
    model_used: str
    tokens_used: int
    latency_ms: int
