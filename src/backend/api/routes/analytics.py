"""Analytics router — no auth required."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.features.conversations.models import Conversation, Message
from backend.features.metrics.models import SystemMetric
from backend.features.requests.models import RequestLog
from backend.features.usage.models import ModelUsageLog

router = APIRouter(tags=["analytics"])


def _since(hours: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


@router.get("/analytics/overview")
async def analytics_overview(
    hours: int = Query(default=24, ge=1, le=720),
    session: AsyncSession = Depends(get_db_session),
):
    since = _since(hours)
    req_count = await session.execute(select(func.count()).select_from(RequestLog).where(RequestLog.created_at >= since))
    total_requests = req_count.scalar() or 0
    tok = await session.execute(select(func.sum(ModelUsageLog.tokens_input), func.sum(ModelUsageLog.tokens_output)).where(ModelUsageLog.created_at >= since))
    row = tok.one()
    tokens_in, tokens_out = int(row[0] or 0), int(row[1] or 0)
    conv_count = await session.execute(select(func.count()).select_from(Conversation).where(Conversation.created_at >= since))
    total_conversations = conv_count.scalar() or 0
    lat = await session.execute(select(func.avg(RequestLog.duration_ms)).where(RequestLog.created_at >= since, RequestLog.duration_ms > 0))
    avg_latency_ms = round(lat.scalar() or 0, 1)
    err_count = await session.execute(select(func.count()).select_from(RequestLog).where(RequestLog.created_at >= since, RequestLog.status == "error"))
    errors = err_count.scalar() or 0
    error_rate = round((errors / total_requests * 100) if total_requests > 0 else 0, 2)
    return {
        "period_hours": hours, "total_requests": total_requests,
        "tokens_input": tokens_in, "tokens_output": tokens_out,
        "total_tokens": tokens_in + tokens_out, "total_conversations": total_conversations,
        "avg_latency_ms": avg_latency_ms, "error_count": errors, "error_rate_percent": error_rate,
    }


@router.get("/analytics/tokens-by-model")
async def tokens_by_model(hours: int = Query(default=24, ge=1, le=720), session: AsyncSession = Depends(get_db_session)):
    since = _since(hours)
    result = await session.execute(
        select(ModelUsageLog.model_name, func.count().label("requests"),
               func.sum(ModelUsageLog.tokens_input).label("tokens_input"),
               func.sum(ModelUsageLog.tokens_output).label("tokens_output"),
               func.sum(ModelUsageLog.total_tokens).label("total_tokens"),
               func.avg(ModelUsageLog.duration_ms).label("avg_latency_ms"))
        .where(ModelUsageLog.created_at >= since)
        .group_by(ModelUsageLog.model_name)
        .order_by(func.sum(ModelUsageLog.total_tokens).desc())
    )
    return {"items": [{"model_name": r.model_name, "requests": int(r.requests),
        "tokens_input": int(r.tokens_input or 0), "tokens_output": int(r.tokens_output or 0),
        "total_tokens": int(r.total_tokens or 0), "avg_latency_ms": round(float(r.avg_latency_ms or 0), 1)} for r in result]}


@router.get("/analytics/requests-timeseries")
async def requests_timeseries(hours: int = Query(default=24, ge=1, le=720), session: AsyncSession = Depends(get_db_session)):
    since = _since(hours)
    result = await session.execute(
        select(func.date_trunc("hour", RequestLog.created_at).label("bucket"),
               func.count().label("requests"),
               func.sum(RequestLog.tokens_input).label("tokens_in"),
               func.sum(RequestLog.tokens_output).label("tokens_out"))
        .where(RequestLog.created_at >= since)
        .group_by(func.date_trunc("hour", RequestLog.created_at))
        .order_by(func.date_trunc("hour", RequestLog.created_at))
    )
    return {"items": [{"bucket": r.bucket.isoformat() if r.bucket else None, "requests": int(r.requests),
        "tokens_in": int(r.tokens_in or 0), "tokens_out": int(r.tokens_out or 0)} for r in result]}


@router.get("/analytics/system-metrics")
async def system_metrics_history(minutes: int = Query(default=60, ge=5, le=1440), session: AsyncSession = Depends(get_db_session)):
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    result = await session.execute(select(SystemMetric).where(SystemMetric.timestamp >= since).order_by(SystemMetric.timestamp.asc()))
    return {"items": [{"timestamp": r.timestamp.isoformat(), "cpu_percent": r.cpu_percent,
        "ram_used_mb": r.ram_used_mb, "ram_total_mb": r.ram_total_mb,
        "gpu_utilization": r.gpu_utilization, "vram_used_mb": r.vram_used_mb, "vram_total_mb": r.vram_total_mb} for r in result.scalars()]}


@router.get("/analytics/top-conversations")
async def top_conversations(hours: int = Query(default=168, ge=1, le=720), limit: int = Query(default=10, ge=1, le=50), session: AsyncSession = Depends(get_db_session)):
    since = _since(hours)
    result = await session.execute(
        select(Message.conversation_id, func.count().label("message_count"), func.sum(Message.token_count).label("total_tokens"))
        .where(Message.created_at >= since).group_by(Message.conversation_id).order_by(func.count().desc()).limit(limit)
    )
    return {"items": [{"conversation_id": str(r.conversation_id), "message_count": int(r.message_count), "total_tokens": int(r.total_tokens or 0)} for r in result]}
