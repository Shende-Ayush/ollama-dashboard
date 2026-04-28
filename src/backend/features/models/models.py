import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.db.base import Base


class ModelRegistryCache(Base):
    __tablename__ = "model_registry_cache"

    model_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    size_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantization: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloaded: Mapped[bool] = mapped_column(Boolean, default=False)
    pulled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelDownloadJob(Base):
    __tablename__ = "model_download_jobs"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True, default="queued")
    percent: Mapped[float] = mapped_column(Float, default=0)
    completed_bytes: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0)
    speed_mbps: Mapped[float] = mapped_column(Float, default=0)
    stop_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelInstance(Base):
    __tablename__ = "model_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(255), index=True)
    loaded_in_gpu: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_usage_mb: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), index=True, default="idle")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
