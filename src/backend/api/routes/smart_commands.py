"""
Smart Command Center — API routes.

AI-powered terminal with suggestions, autocomplete, error detection.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.features.smart_commands.schemas import (
    CommandErrorAnalysisRequest,
    CommandExplainRequest,
    NaturalLanguageCommandRequest,
)
from backend.features.smart_commands.service import smart_command_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smart-commands", tags=["smart-commands"])



@router.post("/natural-language")
async def natural_language_to_command(
    payload: NaturalLanguageCommandRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Convert natural language intent to Ollama commands.

    Example: "Install a coding model optimized for TypeScript"
    Returns ranked command suggestions with explanations.
    """
    try:
        result = await smart_command_service.natural_language_to_command(
            intent=payload.intent,
            context=payload.context,
            session=session,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("Natural language command failed: %s", exc)
        raise HTTPException(500, f"Command generation failed: {str(exc)}")


@router.post("/explain")
async def explain_command(payload: CommandExplainRequest):
    """Explain an Ollama command in plain English.

    Returns a detailed explanation with parameters, side effects,
    and safety level.
    """
    try:
        result = await smart_command_service.explain_command(payload.command)
        return result.model_dump()
    except Exception as exc:
        logger.error("Command explanation failed: %s", exc)
        raise HTTPException(500, f"Explanation failed: {str(exc)}")



@router.post("/analyze-error")
async def analyze_error(
    payload: CommandErrorAnalysisRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Analyze a command error and suggest fixes.

    Uses AI to determine root cause and recommend safe fixes.
    May suggest an auto-fixable command if one exists.
    """
    try:
        result = await smart_command_service.analyze_error(
            command=payload.command,
            error_output=payload.error_output,
            system_context=payload.system_context,
            session=session,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("Error analysis failed: %s", exc)
        raise HTTPException(500, f"Error analysis failed: {str(exc)}")


@router.get("/autocomplete")
async def smart_autocomplete(
    q: str = Query(..., min_length=1, max_length=200, description="Partial input"),
    session: AsyncSession = Depends(get_db_session),
):
    """Get context-aware autocomplete suggestions.

    Combines command knowledge, model catalog, and usage history
    to provide intelligent completions.
    """
    try:
        result = await smart_command_service.get_autocomplete(
            partial_input=q,
            session=session,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("Autocomplete failed: %s", exc)
        raise HTTPException(500, f"Autocomplete failed: {str(exc)}")



@router.post("/track-usage")
async def track_command_usage(
    command: str = Query(..., min_length=1, max_length=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Track command usage for autocomplete improvement."""
    await smart_command_service.track_command_usage(command, session)
    return {"status": "tracked"}
