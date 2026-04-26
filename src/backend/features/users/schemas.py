from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    role: str = Field(default="user", pattern="^(admin|user)$")
    rate_limit_per_min: int = Field(default=60, ge=1, le=10000)
    token_quota_daily: int = Field(default=250000, ge=1000)
    is_active: bool = True
    metadata: dict = Field(default_factory=dict)


class UserUpdateRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|user)$")
    rate_limit_per_min: int | None = Field(default=None, ge=1, le=10000)
    token_quota_daily: int | None = Field(default=None, ge=1000)
    is_active: bool | None = None
    metadata: dict | None = None
