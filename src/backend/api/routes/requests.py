"""Requests router — no auth."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.db.session import get_db_session
from backend.features.requests.models import RequestLog
from backend.schemas.pagination import paginate

router = APIRouter(tags=["requests"])

@router.get("/requests")
async def list_requests(
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(select(RequestLog).order_by(RequestLog.created_at.desc()))
    rows = result.scalars().all()
    items = [{"id": str(r.id), "endpoint": r.endpoint, "method": r.method, "status": r.status,
        "tokens_input": r.tokens_input, "tokens_output": r.tokens_output,
        "duration_ms": r.duration_ms, "error": r.error, "created_at": r.created_at.isoformat()} for r in rows]
    return paginate(items, pg_no=pg_no, pg_size=pg_size).model_dump()
