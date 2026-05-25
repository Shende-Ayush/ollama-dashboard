"""
Health Monitoring & Auto-Recovery — Database models.

Tracks system health checks, incidents, and recovery actions.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.db.base import Base


class HealthCheck(Base):
    """Periodic health check result for a service component."""

    __tablename__ = "health_checks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    component: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )  # ollama, postgres, redis, gpu, disk
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # healthy, degraded, unhealthy, unknown
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )



class HealthIncident(Base):
    """Recorded incident when a component becomes unhealthy."""

    __tablename__ = "health_incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    component: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        String(32), nullable=False, default="warning"
    )  # info, warning, critical
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(32), default="open", index=True
    )  # open, acknowledged, resolved, auto_resolved
    auto_recovery_attempted: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_recovery_successful: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict
    )


class RecoveryAction(Base):
    """Logged auto-recovery action taken by the system."""

    __tablename__ = "recovery_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    component: Mapped[str] = mapped_column(String(128), nullable=False)
    action_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # restart, clear_memory, reconnect, fallback
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending, executing, success, failed
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
