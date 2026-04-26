import hashlib
import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.features.users.models import UserApiClient


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def issue_api_key() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_api_key(raw)


async def require_api_key(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db_session),
) -> UserApiClient:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer API key")
    raw_key = authorization.replace("Bearer ", "", 1).strip()
    key_hash = hash_api_key(raw_key)
    result = await session.execute(select(UserApiClient).where(UserApiClient.api_key_hash == key_hash))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or disabled API key")
    user.last_used_at = datetime.now(timezone.utc)
    await session.commit()
    return user


async def resolve_user_from_token(session: AsyncSession, token: str | None) -> UserApiClient | None:
    if not token:
        return None
    key_hash = hash_api_key(token)
    result = await session.execute(select(UserApiClient).where(UserApiClient.api_key_hash == key_hash))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user
