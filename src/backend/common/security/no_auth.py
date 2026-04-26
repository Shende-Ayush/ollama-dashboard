"""
Stub dependency — auth disabled.
All routes that previously required require_api_key now
inject this anonymous user so the rest of the logic stays intact.
"""
from backend.features.users.models import UserApiClient
import uuid
from datetime import datetime, timezone

_ANON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

def get_anonymous_user() -> UserApiClient:
    """Return a synthetic admin-level user with no rate limits."""
    return UserApiClient(
        id=_ANON_ID,
        name="anonymous",
        api_key_hash="",
        role="admin",
        rate_limit_per_min=10_000,
        token_quota_daily=100_000_000,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_used_at=None,
        metadata_json={},
    )

# Drop-in FastAPI dependency
async def require_api_key() -> UserApiClient:          # noqa: D401
    return get_anonymous_user()

async def resolve_user_from_token(session, token) -> UserApiClient:   # noqa: D401
    return get_anonymous_user()
