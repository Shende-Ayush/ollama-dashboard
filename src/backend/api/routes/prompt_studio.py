"""
Prompt Engineering Studio — API routes.

Full CRUD for templates, versioning, multi-model testing, token analysis.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.features.prompt_studio.schemas import (
    CreatePromptTemplateRequest,
    PromptTestRequest,
    TokenAnalysisRequest,
    UpdatePromptTemplateRequest,
)
from backend.features.prompt_studio.service import prompt_studio_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompt-studio", tags=["prompt-studio"])



@router.post("/templates")
async def create_template(
    payload: CreatePromptTemplateRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new prompt template."""
    result = await prompt_studio_service.create_template(payload, session)
    return result.model_dump()


@router.get("/templates")
async def list_templates(
    search: str | None = None,
    tag: str | None = None,
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """List prompt templates with optional filtering."""
    return await prompt_studio_service.list_templates(
        session, search=search, tag=tag, page=pg_no, page_size=pg_size
    )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get a specific prompt template."""
    try:
        result = await prompt_studio_service.get_template(template_id, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    payload: UpdatePromptTemplateRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Update a prompt template. Creates new version if content changes."""
    try:
        result = await prompt_studio_service.update_template(
            template_id, payload, session
        )
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a prompt template."""
    try:
        await prompt_studio_service.delete_template(template_id, session)
        return {"status": "deleted"}
    except ValueError as exc:
        raise HTTPException(404, str(exc))



@router.get("/templates/{template_id}/versions")
async def get_versions(
    template_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get version history for a template."""
    versions = await prompt_studio_service.get_versions(template_id, session)
    return {"items": [v.model_dump() for v in versions]}


@router.post("/templates/{template_id}/restore/{version_number}")
async def restore_version(
    template_id: str,
    version_number: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Restore a template to a specific version."""
    try:
        result = await prompt_studio_service.restore_version(
            template_id, version_number, session
        )
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/test")
async def test_prompt(
    payload: PromptTestRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Test a prompt against one or more models.

    Runs the prompt through each specified model and returns
    comparative results including latency, token counts, and outputs.
    """
    try:
        result = await prompt_studio_service.test_prompt_multi_model(
            prompt=payload.prompt,
            models=payload.models,
            template_id=payload.template_id,
            variables=payload.variables,
            session=session,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("Prompt test failed: %s", exc)
        raise HTTPException(500, f"Prompt test failed: {str(exc)}")


@router.post("/analyze-tokens")
async def analyze_tokens(payload: TokenAnalysisRequest):
    """Analyze token usage of a prompt text.

    Returns breakdown of token estimates, context window usage percentages,
    and content type analysis.
    """
    result = prompt_studio_service.analyze_tokens(payload.text)
    return result.model_dump()
