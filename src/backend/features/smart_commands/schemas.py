"""
Smart Command Center — Request/Response schemas.

Pydantic models for API validation and serialization.
"""
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class NaturalLanguageCommandRequest(BaseModel):
    """Convert natural language to an Ollama command."""

    intent: str = Field(..., min_length=1, max_length=1000, description="Natural language description of what user wants to do")
    context: Optional[str] = Field(default=None, max_length=2000, description="Additional context (e.g., current models loaded)")


class CommandExplainRequest(BaseModel):
    """Explain an Ollama command in plain English."""

    command: str = Field(..., min_length=1, max_length=500, description="The command to explain")


class CommandErrorAnalysisRequest(BaseModel):
    """Analyze an error and suggest fixes."""

    command: str = Field(..., min_length=1, max_length=500, description="Command that failed")
    error_output: str = Field(..., min_length=1, max_length=5000, description="Error output from the command")
    system_context: Optional[dict] = Field(default=None, description="System state at time of error")


class CommandAutoFixRequest(BaseModel):
    """Request auto-fix for a detected error."""

    analysis_id: str = Field(..., description="ID of the error analysis to apply fix from")


class SmartAutocompleteRequest(BaseModel):
    """Get intelligent autocomplete suggestions."""

    partial_input: str = Field(..., min_length=1, max_length=200, description="Partial command input")
    cursor_position: int = Field(default=-1, description="Cursor position in input")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class CommandSuggestionResponse(BaseModel):
    """AI-generated command suggestion."""

    suggested_command: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    is_safe: bool
    warnings: list[str] = Field(default_factory=list)


class NaturalLanguageCommandResponse(BaseModel):
    """Response for natural language to command conversion."""

    suggestions: list[CommandSuggestionResponse]
    intent_understood: str
    model_used: str


class CommandExplanation(BaseModel):
    """Plain English explanation of a command."""

    command: str
    summary: str
    detailed_explanation: str
    parameters: list[dict]
    side_effects: list[str]
    safety_level: str  # safe, caution, dangerous


class ErrorAnalysisResponse(BaseModel):
    """AI analysis of a command error."""

    id: str
    command: str
    root_cause: str
    suggested_fix: str
    fix_command: Optional[str]
    severity: str
    auto_fixable: bool
    additional_context: str = ""


class AutocompleteItem(BaseModel):
    """Single autocomplete suggestion."""

    completion: str
    description: str
    category: str  # command, model, flag, history
    score: float = Field(ge=0.0, le=1.0)


class SmartAutocompleteResponse(BaseModel):
    """Intelligent autocomplete response."""

    items: list[AutocompleteItem]
    partial_input: str
