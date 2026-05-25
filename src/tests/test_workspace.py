"""
Tests for Sprint 2: Workspace & File System.

Covers workspace CRUD, file operations, path traversal prevention,
git operations, and search functionality.
"""
import asyncio
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.features.workspace.filesystem import FileSystemService
from backend.features.workspace.git_service import GitService
from backend.features.workspace.models import Workspace
from backend.features.workspace.schemas import (
    CreateWorkspaceRequest,
    FileNode,
    GitStatusResponse,
    SearchResult,
)
from backend.features.workspace.service import WorkspaceService
from backend.utils.security.path_validator import PathValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_workspace():
    """Create a temporary workspace directory."""
    path = tempfile.mkdtemp(prefix="test_workspace_")
    yield path
    shutil.rmtree(path, ignore_errors=True)



@pytest.fixture
def fs_service(tmp_workspace):
    """FileSystemService bound to temp directory."""
    return FileSystemService(tmp_workspace)


@pytest.fixture
def git_service(tmp_workspace):
    """GitService bound to temp directory."""
    return GitService(tmp_workspace)


@pytest_asyncio.fixture
async def workspace_service_with_db(db_session, tmp_workspace):
    """WorkspaceService with a real DB session and custom base path."""
    svc = WorkspaceService()
    svc.WORKSPACE_BASE = tmp_workspace
    return svc


# ---------------------------------------------------------------------------
# FileSystemService Tests
# ---------------------------------------------------------------------------
class TestFileSystemService:
    """Tests for file system operations."""

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, fs_service, tmp_workspace):
        """Write a file and read it back."""
        await fs_service.write_file("hello.txt", "Hello, World!")
        content = await fs_service.read_file("hello.txt")
        assert content == "Hello, World!"

    @pytest.mark.asyncio
    async def test_write_nested_file(self, fs_service, tmp_workspace):
        """Write a file in nested directories."""
        await fs_service.write_file("src/main.py", "print('hi')")
        content = await fs_service.read_file("src/main.py")
        assert content == "print('hi')"


    @pytest.mark.asyncio
    async def test_delete_file(self, fs_service, tmp_workspace):
        """Delete a file."""
        await fs_service.write_file("to_delete.txt", "bye")
        await fs_service.delete_file("to_delete.txt")
        exists = await fs_service.file_exists("to_delete.txt")
        assert exists is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self, fs_service):
        """Delete nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await fs_service.delete_file("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, fs_service):
        """Read nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await fs_service.read_file("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_create_directory(self, fs_service, tmp_workspace):
        """Create a directory."""
        await fs_service.create_directory("new_dir/sub_dir")
        assert os.path.isdir(os.path.join(tmp_workspace, "new_dir/sub_dir"))

    @pytest.mark.asyncio
    async def test_list_tree(self, fs_service, tmp_workspace):
        """List directory tree."""
        await fs_service.write_file("file1.py", "# python")
        await fs_service.write_file("file2.js", "// js")
        await fs_service.create_directory("subdir")

        tree = await fs_service.list_tree()
        names = {node.name for node in tree}
        assert "file1.py" in names
        assert "file2.js" in names
        assert "subdir" in names


    @pytest.mark.asyncio
    async def test_list_tree_detects_language(self, fs_service):
        """Language detection from extension."""
        await fs_service.write_file("app.py", "pass")
        await fs_service.write_file("index.ts", "export {}")

        tree = await fs_service.list_tree()
        langs = {node.name: node.language for node in tree}
        assert langs["app.py"] == "python"
        assert langs["index.ts"] == "typescript"

    @pytest.mark.asyncio
    async def test_file_exists(self, fs_service):
        """Check file existence."""
        await fs_service.write_file("exists.txt", "yes")
        assert await fs_service.file_exists("exists.txt") is True
        assert await fs_service.file_exists("nope.txt") is False

    @pytest.mark.asyncio
    async def test_get_file_info(self, fs_service):
        """Get file metadata."""
        await fs_service.write_file("info.py", "x = 1")
        info = await fs_service.get_file_info("info.py")
        assert info["path"] == "info.py"
        assert info["is_directory"] is False
        assert info["language"] == "python"
        assert info["size_bytes"] > 0
        assert info["content_hash"] is not None

    @pytest.mark.asyncio
    async def test_search_filename(self, fs_service):
        """Search by filename."""
        await fs_service.write_file("main.py", "pass")
        await fs_service.write_file("utils.py", "pass")
        await fs_service.write_file("readme.md", "# hi")

        results = await fs_service.search("main")
        assert any(r.path == "main.py" for r in results)


    @pytest.mark.asyncio
    async def test_search_content(self, fs_service):
        """Search file content."""
        await fs_service.write_file("app.py", "def hello():\n    return 'world'\n")
        await fs_service.write_file("lib.py", "x = 42\n")

        results = await fs_service.search("hello", include_content=True)
        assert any(r.line_number == 1 and "hello" in r.match_text for r in results)

    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self, fs_service):
        """Path traversal attempts should be blocked."""
        with pytest.raises(PathValidationError):
            await fs_service.read_file("../../etc/passwd")

    @pytest.mark.asyncio
    async def test_path_traversal_write(self, fs_service):
        """Path traversal on write should be blocked."""
        with pytest.raises(PathValidationError):
            await fs_service.write_file("../../../tmp/evil.txt", "bad")

    @pytest.mark.asyncio
    async def test_path_traversal_delete(self, fs_service):
        """Path traversal on delete should be blocked."""
        with pytest.raises(PathValidationError):
            await fs_service.delete_file("../../etc/passwd")


# ---------------------------------------------------------------------------
# GitService Tests
# ---------------------------------------------------------------------------
class TestGitService:
    """Tests for git operations."""

    @pytest.mark.asyncio
    async def test_git_init(self, git_service, tmp_workspace):
        """Initialize a git repo."""
        await git_service.init()
        assert os.path.isdir(os.path.join(tmp_workspace, ".git"))


    @pytest.mark.asyncio
    async def test_git_status_clean(self, git_service, tmp_workspace):
        """Status of empty initialized repo."""
        await git_service.init()
        # Configure git user for commits
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.email", "test@test.com",
            cwd=tmp_workspace
        )
        await proc.wait()
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.name", "Test User",
            cwd=tmp_workspace
        )
        await proc.wait()

        # Create initial commit so branch exists
        open(os.path.join(tmp_workspace, ".gitkeep"), "w").close()
        proc = await asyncio.create_subprocess_exec(
            "git", "add", "-A", cwd=tmp_workspace
        )
        await proc.wait()
        proc = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", "init", cwd=tmp_workspace
        )
        await proc.wait()

        status = await git_service.status()
        assert status.clean is True
        assert status.branch in ("main", "master")

    @pytest.mark.asyncio
    async def test_git_commit_and_log(self, git_service, tmp_workspace):
        """Commit a file and check log."""
        await git_service.init()
        # Configure git
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.email", "test@test.com",
            cwd=tmp_workspace
        )
        await proc.wait()
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.name", "Test User",
            cwd=tmp_workspace
        )
        await proc.wait()


        # Write a file and commit
        with open(os.path.join(tmp_workspace, "test.txt"), "w") as f:
            f.write("hello git")

        commit_hash = await git_service.commit("Initial commit")
        assert len(commit_hash) == 40  # SHA-1 hash

        log = await git_service.log()
        assert len(log) == 1
        assert log[0]["message"] == "Initial commit"
        assert log[0]["hash"] == commit_hash

    @pytest.mark.asyncio
    async def test_git_diff(self, git_service, tmp_workspace):
        """Check diff after modifying a file."""
        await git_service.init()
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.email", "test@test.com",
            cwd=tmp_workspace
        )
        await proc.wait()
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.name", "Test User",
            cwd=tmp_workspace
        )
        await proc.wait()

        # Initial commit
        with open(os.path.join(tmp_workspace, "file.txt"), "w") as f:
            f.write("line1\n")
        await git_service.commit("first")

        # Modify
        with open(os.path.join(tmp_workspace, "file.txt"), "w") as f:
            f.write("line1\nline2\n")

        diff = await git_service.diff()
        assert "line2" in diff.diff_text

    @pytest.mark.asyncio
    async def test_git_status_with_changes(self, git_service, tmp_workspace):
        """Status shows untracked and modified files."""
        await git_service.init()
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.email", "test@test.com",
            cwd=tmp_workspace
        )
        await proc.wait()
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.name", "Test User",
            cwd=tmp_workspace
        )
        await proc.wait()


        # Initial commit
        with open(os.path.join(tmp_workspace, "tracked.txt"), "w") as f:
            f.write("original")
        await git_service.commit("init")

        # Modify tracked file
        with open(os.path.join(tmp_workspace, "tracked.txt"), "w") as f:
            f.write("modified")
        # Add untracked file
        with open(os.path.join(tmp_workspace, "new.txt"), "w") as f:
            f.write("new file")

        status = await git_service.status()
        assert status.clean is False
        assert "tracked.txt" in status.modified
        assert "new.txt" in status.untracked

    @pytest.mark.asyncio
    async def test_git_branch_operations(self, git_service, tmp_workspace):
        """Branch create and list."""
        await git_service.init()
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.email", "test@test.com",
            cwd=tmp_workspace
        )
        await proc.wait()
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.name", "Test User",
            cwd=tmp_workspace
        )
        await proc.wait()

        # Need at least one commit to create branches
        with open(os.path.join(tmp_workspace, ".gitkeep"), "w") as f:
            f.write("")
        await git_service.commit("init")

        await git_service.branch_create("feature-branch")
        branches = await git_service.branch_list()
        assert "feature-branch" in branches


# ---------------------------------------------------------------------------
# WorkspaceService Tests (with DB)
# ---------------------------------------------------------------------------
class TestWorkspaceService:
    """Tests for workspace service with database."""

    @pytest.mark.asyncio
    async def test_create_workspace(self, workspace_service_with_db, db_session):
        """Create a workspace."""
        svc = workspace_service_with_db
        request = CreateWorkspaceRequest(name="Test Project", description="A test")
        result = await svc.create_workspace(request, db_session)


        assert result.name == "Test Project"
        assert result.description == "A test"
        assert result.is_active is True
        assert os.path.isdir(result.root_path)

    @pytest.mark.asyncio
    async def test_list_workspaces(self, workspace_service_with_db, db_session):
        """List workspaces."""
        svc = workspace_service_with_db
        await svc.create_workspace(
            CreateWorkspaceRequest(name="WS1"), db_session
        )
        await svc.create_workspace(
            CreateWorkspaceRequest(name="WS2"), db_session
        )
        workspaces = await svc.list_workspaces(db_session)
        assert len(workspaces) >= 2
        names = {w.name for w in workspaces}
        assert "WS1" in names
        assert "WS2" in names

    @pytest.mark.asyncio
    async def test_get_workspace(self, workspace_service_with_db, db_session):
        """Get a single workspace."""
        svc = workspace_service_with_db
        created = await svc.create_workspace(
            CreateWorkspaceRequest(name="GetMe"), db_session
        )
        fetched = await svc.get_workspace(created.id, db_session)
        assert fetched.name == "GetMe"
        assert fetched.id == created.id

    @pytest.mark.asyncio
    async def test_get_workspace_not_found(self, workspace_service_with_db, db_session):
        """Get nonexistent workspace raises ValueError."""
        svc = workspace_service_with_db
        fake_id = str(uuid.uuid4())
        with pytest.raises(ValueError, match="not found"):
            await svc.get_workspace(fake_id, db_session)

    @pytest.mark.asyncio
    async def test_delete_workspace(self, workspace_service_with_db, db_session):
        """Delete (deactivate) a workspace."""
        svc = workspace_service_with_db
        created = await svc.create_workspace(
            CreateWorkspaceRequest(name="DeleteMe"), db_session
        )
        await svc.delete_workspace(created.id, db_session)
        # Should not appear in active list
        workspaces = await svc.list_workspaces(db_session)
        ids = {w.id for w in workspaces}
        assert created.id not in ids


    @pytest.mark.asyncio
    async def test_file_operations(self, workspace_service_with_db, db_session):
        """Write, read, and delete files through workspace service."""
        svc = workspace_service_with_db
        ws = await svc.create_workspace(
            CreateWorkspaceRequest(name="FileOps"), db_session
        )

        # Write
        result = await svc.write_file(ws.id, "test.py", "print('hi')", db_session)
        assert result["status"] == "written"

        # Read
        content = await svc.read_file(ws.id, "test.py", db_session)
        assert content.content == "print('hi')"
        assert content.language == "python"

        # Tree
        tree = await svc.get_file_tree(ws.id, db_session)
        names = {n.name for n in tree}
        assert "test.py" in names

        # Delete
        result = await svc.delete_file(ws.id, "test.py", db_session)
        assert result["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_search_files(self, workspace_service_with_db, db_session):
        """Search files through workspace service."""
        svc = workspace_service_with_db
        ws = await svc.create_workspace(
            CreateWorkspaceRequest(name="SearchWS"), db_session
        )
        await svc.write_file(ws.id, "main.py", "def main(): pass", db_session)
        await svc.write_file(ws.id, "utils.py", "def util(): pass", db_session)

        results = await svc.search_files(ws.id, "main", db_session)
        assert any("main" in r.path or "main" in r.match_text for r in results)

    @pytest.mark.asyncio
    async def test_git_operations(self, workspace_service_with_db, db_session):
        """Git operations through workspace service."""
        svc = workspace_service_with_db
        ws = await svc.create_workspace(
            CreateWorkspaceRequest(name="GitWS"), db_session
        )

        # Configure git in workspace
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.email", "test@test.com",
            cwd=ws.root_path
        )
        await proc.wait()
        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.name", "Test User",
            cwd=ws.root_path
        )
        await proc.wait()


        # Write and commit
        await svc.write_file(ws.id, "code.py", "x = 1", db_session)
        commit_result = await svc.git_commit(
            ws.id, "add code.py", None, db_session
        )
        assert commit_result["status"] == "committed"
        assert len(commit_result["hash"]) == 40

        # Status should be clean after commit
        status = await svc.git_status(ws.id, db_session)
        assert status.clean is True

        # Log
        log = await svc.git_log(ws.id, 10, db_session)
        assert len(log) >= 1
        assert log[0]["message"] == "add code.py"

    @pytest.mark.asyncio
    async def test_path_traversal_via_service(
        self, workspace_service_with_db, db_session
    ):
        """Path traversal through workspace service should fail."""
        svc = workspace_service_with_db
        ws = await svc.create_workspace(
            CreateWorkspaceRequest(name="SecureWS"), db_session
        )
        with pytest.raises(PathValidationError):
            await svc.read_file(ws.id, "../../etc/passwd", db_session)
        with pytest.raises(PathValidationError):
            await svc.write_file(
                ws.id, "../../../tmp/evil.txt", "bad", db_session
            )
