"""
Workspace & File System — High-level service orchestrator.

Coordinates workspace CRUD, file operations, and git operations.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.features.workspace.filesystem import FileSystemService
from backend.features.workspace.git_service import GitService
from backend.features.workspace.models import Workspace
from backend.features.workspace.schemas import (
    CreateWorkspaceRequest,
    FileContentResponse,
    FileNode,
    GitDiffResponse,
    GitStatusResponse,
    SearchResult,
    WorkspaceResponse,
)

logger = logging.getLogger(__name__)


class WorkspaceService:
    """High-level workspace management orchestrator."""

    WORKSPACE_BASE = os.environ.get("WORKSPACE_BASE", "/tmp/ollama-workspaces")

    async def _get_workspace(self, workspace_id: str, session: AsyncSession) -> Workspace:
        """Retrieve workspace by ID or raise ValueError."""
        try:
            ws_uuid = uuid.UUID(workspace_id)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid workspace ID: {workspace_id}")

        result = await session.execute(
            select(Workspace).where(Workspace.id == ws_uuid)
        )
        workspace = result.scalar_one_or_none()
        if workspace is None:
            raise ValueError(f"Workspace not found: {workspace_id}")
        return workspace

    def _to_response(self, workspace: Workspace) -> WorkspaceResponse:
        """Convert ORM model to response schema."""
        return WorkspaceResponse(
            id=str(workspace.id),
            name=workspace.name,
            description=workspace.description or "",
            root_path=workspace.root_path,
            git_url=workspace.git_url,
            is_active=workspace.is_active,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )

    # -----------------------------------------------------------------------
    # Workspace CRUD
    # -----------------------------------------------------------------------
    async def create_workspace(
        self, request: CreateWorkspaceRequest, session: AsyncSession
    ) -> WorkspaceResponse:
        """Create a new workspace with a directory on disk."""
        workspace_id = uuid.uuid4()
        root_path = os.path.join(self.WORKSPACE_BASE, str(workspace_id))

        # Create workspace directory
        os.makedirs(root_path, exist_ok=True)

        workspace = Workspace(
            id=workspace_id,
            name=request.name,
            description=request.description,
            root_path=root_path,
            git_url=request.git_url,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(workspace)
        await session.commit()
        await session.refresh(workspace)

        # Initialize git if git_url provided or by default
        git_svc = GitService(root_path)
        try:
            await git_svc.init()
        except RuntimeError:
            logger.warning("Failed to initialize git for workspace %s", workspace_id)

        return self._to_response(workspace)

    async def get_workspace(
        self, workspace_id: str, session: AsyncSession
    ) -> WorkspaceResponse:
        """Get a single workspace by ID."""
        workspace = await self._get_workspace(workspace_id, session)
        return self._to_response(workspace)

    async def list_workspaces(self, session: AsyncSession) -> list[WorkspaceResponse]:
        """List all active workspaces."""
        result = await session.execute(
            select(Workspace).where(Workspace.is_active).order_by(Workspace.created_at.desc())
        )
        workspaces = result.scalars().all()
        return [self._to_response(ws) for ws in workspaces]

    async def delete_workspace(
        self, workspace_id: str, session: AsyncSession
    ) -> None:
        """Soft-delete a workspace (mark inactive)."""
        workspace = await self._get_workspace(workspace_id, session)
        workspace.is_active = False
        workspace.updated_at = datetime.now(timezone.utc)
        await session.commit()

    # -----------------------------------------------------------------------
    # File Operations (delegates to FileSystemService)
    # -----------------------------------------------------------------------
    async def get_file_tree(
        self, workspace_id: str, session: AsyncSession
    ) -> list[FileNode]:
        """Get file tree for a workspace."""
        workspace = await self._get_workspace(workspace_id, session)
        fs = FileSystemService(workspace.root_path)
        return await fs.list_tree()

    async def read_file(
        self, workspace_id: str, path: str, session: AsyncSession
    ) -> FileContentResponse:
        """Read a file from workspace."""
        workspace = await self._get_workspace(workspace_id, session)
        fs = FileSystemService(workspace.root_path)
        content = await fs.read_file(path)
        info = await fs.get_file_info(path)
        return FileContentResponse(
            path=path,
            content=content,
            language=info.get("language"),
            size_bytes=info.get("size_bytes", 0),
        )

    async def write_file(
        self, workspace_id: str, path: str, content: str, session: AsyncSession
    ) -> dict:
        """Write a file to workspace."""
        workspace = await self._get_workspace(workspace_id, session)
        fs = FileSystemService(workspace.root_path)
        await fs.write_file(path, content)
        info = await fs.get_file_info(path)
        return {"status": "written", "path": path, **info}

    async def delete_file(
        self, workspace_id: str, path: str, session: AsyncSession
    ) -> dict:
        """Delete a file from workspace."""
        workspace = await self._get_workspace(workspace_id, session)
        fs = FileSystemService(workspace.root_path)
        await fs.delete_file(path)
        return {"status": "deleted", "path": path}

    async def search_files(
        self, workspace_id: str, query: str, session: AsyncSession, include_content: bool = False
    ) -> list[SearchResult]:
        """Search files in workspace."""
        workspace = await self._get_workspace(workspace_id, session)
        fs = FileSystemService(workspace.root_path)
        return await fs.search(query, include_content=include_content)

    # -----------------------------------------------------------------------
    # Git Operations (delegates to GitService)
    # -----------------------------------------------------------------------
    async def git_status(
        self, workspace_id: str, session: AsyncSession
    ) -> GitStatusResponse:
        """Get git status for workspace."""
        workspace = await self._get_workspace(workspace_id, session)
        git = GitService(workspace.root_path)
        return await git.status()

    async def git_commit(
        self,
        workspace_id: str,
        message: str,
        files: list[str] | None,
        session: AsyncSession,
    ) -> dict:
        """Commit changes in workspace."""
        workspace = await self._get_workspace(workspace_id, session)
        git = GitService(workspace.root_path)
        commit_hash = await git.commit(message, files)
        return {"status": "committed", "hash": commit_hash}

    async def git_diff(
        self, workspace_id: str, session: AsyncSession
    ) -> GitDiffResponse:
        """Get git diff for workspace."""
        workspace = await self._get_workspace(workspace_id, session)
        git = GitService(workspace.root_path)
        return await git.diff()

    async def git_log(
        self, workspace_id: str, limit: int, session: AsyncSession
    ) -> list[dict]:
        """Get git log for workspace."""
        workspace = await self._get_workspace(workspace_id, session)
        git = GitService(workspace.root_path)
        return await git.log(limit=limit)


# Module-level singleton
workspace_service = WorkspaceService()
