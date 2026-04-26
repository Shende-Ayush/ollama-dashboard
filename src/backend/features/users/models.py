import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.db.base import Base


class UserApiClient(Base):
    __tablename__ = "users_api_clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    token_quota_daily: Mapped[int] = mapped_column(Integer, nullable=False, default=250000)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
