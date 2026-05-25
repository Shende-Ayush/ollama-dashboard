"""Pydantic schemas for code execution sandbox."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    """Request to execute code in a sandboxed environment."""

    code: str = Field(..., min_length=1, max_length=50000, description="Code to execute")
    language: str = Field(..., min_length=1, description="Programming language")
    stdin: str | None = Field(default=None, description="Standard input for the program")
    timeout: int = Field(default=30, ge=1, le=120, description="Timeout in seconds")
    memory_mb: int = Field(default=128, ge=32, le=512, description="Memory limit in MB")


class ExecutionResponse(BaseModel):
    """Response with code execution results."""

    id: UUID
    language: str
    status: str
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    memory_used_mb: float | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RuntimeInfo(BaseModel):
    """Information about a supported runtime environment."""

    name: str
    language: str
    docker_image: str
    max_timeout: int
    max_memory_mb: int
    is_active: bool = True


class ValidationResult(BaseModel):
    """Result of code safety validation."""

    is_safe: bool
    violations: list[str] = Field(default_factory=list)
    risk_level: str  # low, medium, high, critical


class ValidateRequest(BaseModel):
    """Request to validate code safety."""

    code: str = Field(..., min_length=1, description="Code to validate")
    language: str = Field(..., min_length=1, description="Programming language")
