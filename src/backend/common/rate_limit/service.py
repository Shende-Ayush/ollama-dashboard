from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.rate_limit.models import RateLimitTracking
from backend.features.users.models import UserApiClient


async def enforce_rate_limits(session: AsyncSession, user: UserApiClient, token_cost: int = 0) -> None:
    now = datetime.now(timezone.utc)
    window_start = now.replace(second=0, microsecond=0)
    result = await session.execute(
        select(RateLimitTracking).where(
            RateLimitTracking.user_id == user.id,
            RateLimitTracking.window_start == window_start,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        entry = RateLimitTracking(user_id=user.id, window_start=window_start, request_count=0, tokens_used=0)
        session.add(entry)
    if entry.request_count >= user.rate_limit_per_min:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    # Daily quota via last 24h approximation over this table + request logs.
    start_day = now - timedelta(days=1)
    result_quota = await session.execute(
        select(RateLimitTracking).where(
            RateLimitTracking.user_id == user.id,
            RateLimitTracking.window_start >= start_day,
        )
    )
    used = sum(item.tokens_used for item in result_quota.scalars().all())
    if used + token_cost > user.token_quota_daily:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily token quota exceeded")
    entry.request_count += 1
    entry.tokens_used += token_cost
    await session.commit()
