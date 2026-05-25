"""
Smart Command Center — Database models.

Stores AI-generated command suggestions, error analysis results,
and intelligent autocomplete context.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.db.base import Base


class CommandSuggestion(Base):
    """AI-generated command suggestions based on user intent."""

    __tablename__ = "command_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_command: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    model_used: Mapped[str] = mapped_column(String(255), nullable=False)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class CommandErrorAnalysis(Base):
    """AI analysis of command errors with fix suggestions."""

    __tablename__ = "command_error_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    error_output: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[str] = mapped_column(Text, nullable=False)
    fix_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="medium")  # low, medium, high, critical
    auto_fixable: Mapped[bool] = mapped_column(Boolean, default=False)
    model_used: Mapped[str] = mapped_column(String(255), nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class CommandContext(Base):
    """Contextual data for intelligent autocomplete — tracks patterns and frequent commands."""

    __tablename__ = "command_contexts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    command_pattern: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    frequency: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    context_data: Mapped[dict] = mapped_column(JSONB, default=dict)
