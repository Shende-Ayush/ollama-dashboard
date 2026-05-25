"""AI Coding — API routes for completion and code actions."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.db.session import get_db_session
from backend.features.ai_coding.schemas import (
    CodeActionRequest,
    CompletionRequest,
)
from backend.features.ai_coding.completion.service import completion_service
from backend.features.ai_coding.completion.cache import completion_cache
from backend.features.ai_coding.actions.service import code_action_service
from backend.services.model_provider.registry import model_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-coding", tags=["ai-coding"])


@router.post("/complete")
async def complete_code(
    payload: CompletionRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Generate inline code completion.
    
    Uses Fill-in-Middle (FIM) prompting with the best available coding model.
    Results are cached for repeat queries.
    """
    try:
        result = await completion_service.complete(payload, session)
        return result.model_dump()
    except Exception as exc:
        logger.error("Completion failed: %s", exc)
        raise HTTPException(500, f"Completion failed: {str(exc)}")


@router.post("/code-action")
async def execute_code_action(payload: CodeActionRequest):
    """Execute a code action (explain, refactor, optimize, fix, add_docs, add_tests)."""
    try:
        result = await code_action_service.execute(payload)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error("Code action failed: %s", exc)
        raise HTTPException(500, f"Code action failed: {str(exc)}")


@router.get("/cache/stats")
async def cache_stats():
    """Get completion cache statistics."""
    return completion_cache.stats


@router.post("/cache/clear")
async def clear_cache():
    """Clear the completion cache."""
    completion_cache._cache.clear()
    completion_cache._hits = 0
    completion_cache._misses = 0
    return {"status": "cleared"}


@router.get("/models")
async def list_coding_models():
    """List available coding models with FIM capability."""
    from backend.features.ai_coding.completion.model_router import model_router, COMPLETION_MODELS
    provider = model_registry.get("ollama")
    try:
        available = await provider.list_models()
        models = [
            {
                "name": m.name,
                "supports_fim": model_router.supports_fim(m.name),
                "size_bytes": m.size_bytes,
                "family": m.family,
            }
            for m in available
        ]
    except Exception:
        models = []
    
    return {
        "models": models,
        "preferred_by_language": COMPLETION_MODELS,
    }
