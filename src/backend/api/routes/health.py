"""
Health Monitoring & Auto-Recovery — API routes.

Endpoints for system health checks, incident management,
and recovery actions.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.features.health.schemas import RecoveryTriggerRequest
from backend.features.health.service import health_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])



@router.get("/system")
async def system_health(
    session: AsyncSession = Depends(get_db_session),
):
    """Run full system health check across all components.

    Checks: Ollama, PostgreSQL, GPU, Disk.
    Auto-creates incidents for unhealthy components and
    attempts recovery if possible.
    """
    try:
        result = await health_service.check_system_health(session)
        return result.model_dump()
    except Exception as exc:
        logger.error("System health check failed: %s", exc)
        raise HTTPException(500, f"Health check failed: {str(exc)}")


@router.get("/incidents")
async def list_incidents(
    status: str | None = None,
    component: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """List health incidents with optional filtering."""
    incidents = await health_service.list_incidents(
        session, status=status, component=component, limit=limit
    )
    return {"items": [i.model_dump() for i in incidents]}


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Manually resolve an incident."""
    try:
        await health_service.resolve_incident(incident_id, session)
        return {"status": "resolved"}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/recover")
async def trigger_recovery(
    payload: RecoveryTriggerRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Manually trigger a recovery action for a component."""
    try:
        result = await health_service.trigger_recovery(
            component=payload.component,
            action_type=payload.action_type,
            session=session,
        )
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error("Recovery trigger failed: %s", exc)
        raise HTTPException(500, f"Recovery failed: {str(exc)}")


@router.get("/recovery-actions")
async def list_recovery_actions(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """List recent recovery actions."""
    actions = await health_service.list_recovery_actions(session, limit=limit)
    return {"items": [a.model_dump() for a in actions]}
