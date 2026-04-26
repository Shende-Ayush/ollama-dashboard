"""Usage router — no auth."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.db.session import get_db_session
from backend.features.usage.models import ModelUsageLog

router = APIRouter(tags=["usage"])

@router.get("/usage/tokens")
async def usage_tokens(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(ModelUsageLog.model_name,
               func.sum(ModelUsageLog.tokens_input).label("tokens_input"),
               func.sum(ModelUsageLog.tokens_output).label("tokens_output"),
               func.sum(ModelUsageLog.total_tokens).label("total_tokens"))
        .group_by(ModelUsageLog.model_name)
    )
    return {"items": [{"model_name": r.model_name, "tokens_input": int(r.tokens_input or 0),
        "tokens_output": int(r.tokens_output or 0), "total_tokens": int(r.total_tokens or 0)} for r in result]}
