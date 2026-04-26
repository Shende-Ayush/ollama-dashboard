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
    u = UserApiClient.__new__(UserApiClient)
    u.id                = _ANON_ID
    u.name              = "anonymous"
    u.api_key_hash      = ""
    u.role              = "admin"
    u.rate_limit_per_min = 10_000
    u.token_quota_daily  = 100_000_000
    u.is_active          = True
    u.created_at         = datetime.now(timezone.utc)
    u.last_used_at       = None
    u.metadata_json      = {}
    return u

# Drop-in FastAPI dependency
async def require_api_key() -> UserApiClient:          # noqa: D401
    return get_anonymous_user()

async def resolve_user_from_token(session, token) -> UserApiClient:   # noqa: D401
    return get_anonymous_user()
