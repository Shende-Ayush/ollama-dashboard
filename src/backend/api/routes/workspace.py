"""
Workspace & File System — API routes.

Provides REST endpoints for workspace management, file operations, and git integration.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.features.workspace.schemas import (
    CreateWorkspaceRequest,
    GitCommitRequest,
    SearchRequest,
    WriteFileRequest,
)
from backend.features.workspace.service import workspace_service
from backend.utils.security.path_validator import PathValidationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------
@router.post("")
async def create_workspace(
    payload: CreateWorkspaceRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new workspace."""
    try:
        result = await workspace_service.create_workspace(payload, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("")
async def list_workspaces(
    session: AsyncSession = Depends(get_db_session),
):
    """List all active workspaces."""
    workspaces = await workspace_service.list_workspaces(session)
    return {"items": [w.model_dump() for w in workspaces]}


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get a specific workspace."""
    try:
        result = await workspace_service.get_workspace(workspace_id, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Delete (deactivate) a workspace."""
    try:
        await workspace_service.delete_workspace(workspace_id, session)
        return {"status": "deleted"}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


# ---------------------------------------------------------------------------
# File Operations
# ---------------------------------------------------------------------------
@router.get("/{workspace_id}/tree")
async def get_file_tree(
    workspace_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get the file tree for a workspace."""
    try:
        tree = await workspace_service.get_file_tree(workspace_id, session)
        return {"tree": [node.model_dump() for node in tree]}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))


@router.get("/{workspace_id}/files/{path:path}")
async def read_file(
    workspace_id: str,
    path: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Read a file from the workspace."""
    try:
        result = await workspace_service.read_file(workspace_id, path, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except PathValidationError as exc:
        raise HTTPException(403, str(exc))


@router.put("/{workspace_id}/files/{path:path}")
async def write_file(
    workspace_id: str,
    path: str,
    payload: WriteFileRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Write/update a file in the workspace."""
    try:
        result = await workspace_service.write_file(
            workspace_id, path, payload.content, session
        )
        return result
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except PathValidationError as exc:
        raise HTTPException(403, str(exc))


@router.delete("/{workspace_id}/files/{path:path}")
async def delete_file(
    workspace_id: str,
    path: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a file from the workspace."""
    try:
        result = await workspace_service.delete_file(workspace_id, path, session)
        return result
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except PathValidationError as exc:
        raise HTTPException(403, str(exc))


@router.post("/{workspace_id}/search")
async def search_files(
    workspace_id: str,
    payload: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Search files in the workspace."""
    try:
        results = await workspace_service.search_files(
            workspace_id, payload.query, session, include_content=payload.include_content
        )
        return {"results": [r.model_dump() for r in results]}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


# ---------------------------------------------------------------------------
# Git Operations
# ---------------------------------------------------------------------------
@router.get("/{workspace_id}/git/status")
async def git_status(
    workspace_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get git status for a workspace."""
    try:
        result = await workspace_service.git_status(workspace_id, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))


@router.post("/{workspace_id}/git/commit")
async def git_commit(
    workspace_id: str,
    payload: GitCommitRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a git commit in the workspace."""
    try:
        result = await workspace_service.git_commit(
            workspace_id, payload.message, payload.files, session
        )
        return result
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))


@router.get("/{workspace_id}/git/diff")
async def git_diff(
    workspace_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get git diff for a workspace."""
    try:
        result = await workspace_service.git_diff(workspace_id, session)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))


@router.get("/{workspace_id}/git/log")
async def git_log(
    workspace_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """Get git log for a workspace."""
    try:
        result = await workspace_service.git_log(workspace_id, limit, session)
        return {"commits": result}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
