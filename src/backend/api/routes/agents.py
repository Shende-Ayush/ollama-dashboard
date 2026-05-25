"""
Agents Framework — API routes.

Multi-agent orchestration endpoints for creating, managing,
executing, and coordinating AI agents.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.features.agents.schemas import (
    AGENT_TYPES,
    CreateAgentRequest,
    ExecuteAgentRequest,
    OrchestrateRequest,
    UpdateAgentRequest,
)
from backend.features.agents.service import agent_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])



@router.get("/types")
async def list_agent_types():
    """List available agent types."""
    return {"types": AGENT_TYPES}


@router.post("")
async def create_agent(
    payload: CreateAgentRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new agent configuration."""
    try:
        result = await agent_service.create_agent(payload, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("")
async def list_agents(
    agent_type: str | None = None,
    active_only: bool = True,
    session: AsyncSession = Depends(get_db_session),
):
    """List all agent configurations."""
    agents = await agent_service.list_agents(
        session, agent_type=agent_type, active_only=active_only
    )
    return {"items": [a.model_dump() for a in agents]}


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get a specific agent configuration."""
    try:
        result = await agent_service.get_agent(agent_id, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    payload: UpdateAgentRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Update an agent configuration."""
    try:
        result = await agent_service.update_agent(agent_id, payload, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Delete an agent configuration."""
    try:
        await agent_service.delete_agent(agent_id, session)
        return {"status": "deleted"}
    except ValueError as exc:
        raise HTTPException(404, str(exc))



@router.post("/execute")
async def execute_agent(
    payload: ExecuteAgentRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Execute a single agent on a task.

    The agent will iterate up to max_iterations, producing
    step-by-step reasoning and a final result.
    """
    try:
        result = await agent_service.execute(
            agent_id=payload.agent_id,
            task=payload.task,
            context=payload.context,
            session=session,
        )
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error("Agent execution failed: %s", exc)
        raise HTTPException(500, f"Execution failed: {str(exc)}")


@router.post("/orchestrate")
async def orchestrate(
    payload: OrchestrateRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Orchestrate multiple agents to complete a task.

    Strategies:
    - sequential: agents run one after another, passing context
    - parallel: agents run independently on the same task
    - pipeline: each agent refines the output of the previous
    """
    try:
        result = await agent_service.orchestrate(
            task=payload.task,
            agent_ids=payload.agent_ids,
            strategy=payload.strategy,
            context=payload.context,
            session=session,
        )
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error("Orchestration failed: %s", exc)
        raise HTTPException(500, f"Orchestration failed: {str(exc)}")


@router.get("/executions/history")
async def list_executions(
    agent_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """List agent execution history."""
    executions = await agent_service.list_executions(
        session, agent_id=agent_id, status=status, limit=limit
    )
    return {"items": [e.model_dump() for e in executions]}


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get a specific execution with full step details."""
    try:
        result = await agent_service.get_execution(execution_id, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))
