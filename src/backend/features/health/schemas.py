"""
Health Monitoring & Auto-Recovery — Schemas.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class ComponentHealth(BaseModel):
    component: str
    status: str  # healthy, degraded, unhealthy, unknown
    response_time_ms: int
    details: dict[str, Any] = Field(default_factory=dict)
    last_checked: Optional[datetime] = None


class SystemHealthResponse(BaseModel):
    overall_status: str  # healthy, degraded, unhealthy
    components: list[ComponentHealth]
    uptime_seconds: int
    checked_at: datetime


class HealthIncidentResponse(BaseModel):
    id: str
    component: str
    severity: str
    title: str
    description: str
    status: str
    auto_recovery_attempted: bool
    auto_recovery_successful: bool
    recovery_action: Optional[str]
    detected_at: datetime
    resolved_at: Optional[datetime]


class RecoveryActionResponse(BaseModel):
    id: str
    incident_id: Optional[str]
    component: str
    action_type: str
    description: str
    status: str
    result: Optional[str]
    executed_at: datetime
    duration_ms: int


class RecoveryTriggerRequest(BaseModel):
    component: str = Field(..., description="Component to recover")
    action_type: str = Field(
        default="restart",
        description="Recovery action: restart, clear_memory, reconnect"
    )
