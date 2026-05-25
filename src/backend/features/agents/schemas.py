"""
Agents Framework — Request/Response schemas.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agent Types
# ---------------------------------------------------------------------------
AGENT_TYPES = [
    "backend_engineer",
    "frontend_engineer",
    "debugger",
    "security_auditor",
    "devops",
    "testing",
    "performance",
    "orchestrator",
]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    agent_type: str = Field(..., description="One of the predefined agent types")
    description: str = Field(default="", max_length=2000)
    system_prompt: str = Field(..., min_length=10, max_length=50000)
    capabilities: list[str] = Field(default_factory=list)
    model_name: str = Field(..., min_length=1, max_length=255)
    max_iterations: int = Field(default=10, ge=1, le=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    system_prompt: Optional[str] = Field(default=None, max_length=50000)
    capabilities: Optional[list[str]] = None
    model_name: Optional[str] = None
    max_iterations: Optional[int] = Field(default=None, ge=1, le=100)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    is_active: Optional[bool] = None


class ExecuteAgentRequest(BaseModel):
    agent_id: str = Field(..., description="Agent config ID")
    task: str = Field(..., min_length=1, max_length=10000)
    context: dict[str, Any] = Field(default_factory=dict)


class OrchestrateRequest(BaseModel):
    """Multi-agent orchestration request."""
    task: str = Field(..., min_length=1, max_length=10000)
    agent_ids: list[str] = Field(
        default_factory=list,
        description="Specific agents to use (empty = auto-select)"
    )
    strategy: str = Field(
        default="sequential",
        description="Execution strategy: sequential, parallel, pipeline"
    )
    context: dict[str, Any] = Field(default_factory=dict)



# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class AgentConfigResponse(BaseModel):
    id: str
    name: str
    agent_type: str
    description: str
    system_prompt: str
    capabilities: list[str]
    model_name: str
    max_iterations: int
    temperature: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AgentStepResponse(BaseModel):
    id: str
    step_number: int
    action: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    status: str
    reasoning: str
    tokens_used: int
    duration_ms: int
    created_at: datetime


class AgentExecutionResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    task: str
    status: str
    result: Optional[str]
    error: Optional[str]
    iterations_used: int
    tokens_consumed: int
    duration_ms: int
    steps: list[AgentStepResponse] = Field(default_factory=list)
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


class OrchestrationResponse(BaseModel):
    """Response for multi-agent orchestration."""
    task: str
    strategy: str
    executions: list[AgentExecutionResponse]
    final_result: str
    total_tokens: int
    total_duration_ms: int
    status: str
