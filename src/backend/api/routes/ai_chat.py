"""AI Chat & Diff Application — API routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.db.session import get_db_session
from backend.features.ai_coding.chat.schemas import ChatRequest
from backend.features.ai_coding.chat.service import editor_chat_service
from backend.features.ai_coding.apply.schemas import (
    ApplyDiffRequest,
    ApplyFromResponseRequest,
    DiffPreviewRequest,
)
from backend.features.ai_coding.apply.diff_applier import diff_applier

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-chat", tags=["ai-chat"])


@router.post("/message")
async def chat_message(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Send a message to the AI coding assistant with optional file context."""
    try:
        result = await editor_chat_service.chat(payload, session)
        return result.model_dump()
    except Exception as exc:
        logger.error("Chat failed: %s", exc)
        raise HTTPException(500, f"Chat failed: {str(exc)}")


@router.post("/diff/preview")
async def preview_diff(
    payload: DiffPreviewRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Preview a diff without applying changes."""
    try:
        diff = await diff_applier.preview_changes(
            workspace_id=payload.workspace_id,
            file_path=payload.file_path,
            new_content=payload.new_content,
            session=session,
        )
        return {
            "file_path": diff.file_path,
            "diff_text": diff.diff_text,
            "insertions": diff.insertions,
            "deletions": diff.deletions,
            "is_new_file": diff.original_content == "",
        }
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.error("Diff preview failed: %s", exc)
        raise HTTPException(500, f"Preview failed: {str(exc)}")


@router.post("/diff/apply")
async def apply_diff(
    payload: ApplyDiffRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Apply a code change to a workspace file."""
    try:
        result = await diff_applier.apply_change(
            workspace_id=payload.workspace_id,
            file_path=payload.file_path,
            new_content=payload.new_content,
            session=session,
        )
        return result
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.error("Diff apply failed: %s", exc)
        raise HTTPException(500, f"Apply failed: {str(exc)}")


@router.post("/diff/apply-from-response")
async def apply_from_ai_response(
    payload: ApplyFromResponseRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Extract code from AI response and apply to workspace files."""
    try:
        results = await diff_applier.apply_from_response(
            workspace_id=payload.workspace_id,
            response_text=payload.response_text,
            target_file=payload.target_file,
            language=payload.language,
            session=session,
        )
        return {"applied": results, "count": len(results)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.error("Apply from response failed: %s", exc)
        raise HTTPException(500, f"Apply failed: {str(exc)}")
