"""Metrics router — no auth."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.db.session import get_db_session
from backend.features.metrics.models import SystemMetric
from backend.schemas.pagination import paginate
from backend.services.ollama_client import OllamaClient

router = APIRouter(tags=["metrics"])

@router.get("/metrics/system/recent")
async def recent_system_metrics(
    minutes: int = Query(default=30, ge=1, le=1440),
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    result = await session.execute(select(SystemMetric).where(SystemMetric.timestamp >= cutoff).order_by(SystemMetric.timestamp.desc()))
    rows = result.scalars().all()
    items = [{"timestamp": r.timestamp.isoformat(), "cpu_percent": r.cpu_percent,
              "ram_used_mb": r.ram_used_mb, "ram_total_mb": r.ram_total_mb,
              "gpu_utilization": r.gpu_utilization, "vram_used_mb": r.vram_used_mb,
              "vram_total_mb": r.vram_total_mb, "container_name": r.container_name} for r in rows]
    return paginate(items, pg_no=pg_no, pg_size=pg_size).model_dump()

@router.get("/metrics/models/active")
async def active_models():
    client = OllamaClient()
    models = await client.list_running()
    return {"items": models}
