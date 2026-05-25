"""Code Execution Sandbox — API routes."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.features.code_execution.schemas import (
    ExecuteRequest,
    ValidateRequest,
)
from backend.features.code_execution.service import execution_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/execute", tags=["code-execution"])


@router.get("/runtimes")
async def list_runtimes():
    """List all supported runtime environments."""
    runtimes = await execution_service.list_runtimes()
    return {"runtimes": [r.model_dump() for r in runtimes]}


@router.post("/validate")
async def validate_code(payload: ValidateRequest):
    """Validate code safety without executing.

    Returns safety assessment including violations and risk level.
    """
    result = await execution_service.validate_code(
        code=payload.code, language=payload.language
    )
    return result.model_dump()


@router.post("")
async def execute_code(
    payload: ExecuteRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Execute code in a sandboxed environment.

    The code is validated for safety, then executed within resource limits.
    Returns execution results including stdout, stderr, exit code, and timing.
    """
    try:
        result = await execution_service.execute(payload, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Code execution failed: %s", exc)
        raise HTTPException(status_code=500, detail="Execution failed")


@router.get("/{execution_id}")
async def get_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get execution result by ID."""
    try:
        result = await execution_service.get_execution(execution_id, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{execution_id}/stop")
async def stop_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Stop a running execution."""
    try:
        result = await execution_service.stop_execution(execution_id, session)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
