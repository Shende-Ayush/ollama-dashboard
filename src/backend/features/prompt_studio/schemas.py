"""
Prompt Engineering Studio — Request/Response schemas.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class CreatePromptTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    template: str = Field(..., min_length=1, max_length=50000)
    variables: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    model_name: Optional[str] = None
    is_public: bool = True


class UpdatePromptTemplateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    template: Optional[str] = Field(default=None, max_length=50000)
    variables: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    model_name: Optional[str] = None
    is_public: Optional[bool] = None
    change_notes: str = Field(default="", max_length=1000)


class PromptTestRequest(BaseModel):
    """Test a prompt against one or more models."""
    prompt: str = Field(..., min_length=1, max_length=50000)
    template_id: Optional[str] = None
    models: list[str] = Field(..., min_length=1, max_length=5)
    variables: dict[str, str] = Field(default_factory=dict)


class TokenAnalysisRequest(BaseModel):
    """Analyze token usage of a prompt."""
    text: str = Field(..., min_length=1, max_length=50000)
    model_name: Optional[str] = None



# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class PromptTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    template: str
    variables: list[str]
    tags: list[str]
    model_name: Optional[str]
    is_public: bool
    usage_count: int
    version_count: int = 0
    created_at: datetime
    updated_at: datetime


class PromptVersionResponse(BaseModel):
    id: str
    template_id: str
    version_number: int
    template_content: str
    variables: list[str]
    change_notes: str
    created_at: datetime


class PromptTestResultResponse(BaseModel):
    model_name: str
    response: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    quality_score: Optional[float]


class MultiModelComparisonResponse(BaseModel):
    prompt: str
    results: list[PromptTestResultResponse]
    best_model: Optional[str]
    summary: str


class TokenAnalysisResponse(BaseModel):
    text_length: int
    estimated_tokens: int
    estimated_cost_context: str
    breakdown: dict[str, Any] = Field(default_factory=dict)
