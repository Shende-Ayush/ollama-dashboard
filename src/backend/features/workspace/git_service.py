"""
Workspace & File System — Git operations service.

Provides git operations via subprocess (git CLI).
Does NOT require gitpython - uses asyncio.create_subprocess_exec.
"""
import asyncio
import logging
import re
from typing import Optional

from backend.features.workspace.schemas import GitDiffResponse, GitStatusResponse

logger = logging.getLogger(__name__)


class GitService:
    """Git operations for a workspace."""

    def __init__(self, repo_path: str):
        self.path = repo_path

    async def _run_git(self, *args: str) -> tuple[str, str, int]:
        """Run a git command and return (stdout, stderr, returncode)."""
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=self.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            stdout.decode("utf-8", errors="replace").rstrip("\n"),
            stderr.decode("utf-8", errors="replace").strip(),
            proc.returncode or 0,
        )

    async def init(self) -> None:
        """Initialize a git repository."""
        stdout, stderr, rc = await self._run_git("init")
        if rc != 0:
            raise RuntimeError(f"git init failed: {stderr}")

    async def status(self) -> GitStatusResponse:
        """Get repository status."""
        branch = await self.branch_current()

        stdout, stderr, rc = await self._run_git("status", "--porcelain=v1")
        if rc != 0:
            raise RuntimeError(f"git status failed: {stderr}")

        modified: list[str] = []
        untracked: list[str] = []
        staged: list[str] = []

        for line in stdout.splitlines():
            if len(line) < 4:
                continue
            # Porcelain v1 format: XY<space>filename
            # X = index status, Y = worktree status
            index_status = line[0]
            worktree_status = line[1]
            # Filename starts after "XY " (position 3)
            filepath = line[3:]

            # Remove quotes if present
            if filepath.startswith('"') and filepath.endswith('"'):
                filepath = filepath[1:-1]

            # Handle rename format: "R  old -> new"
            if " -> " in filepath:
                filepath = filepath.split(" -> ")[-1]

            filepath = filepath.strip()

            if index_status == "?":
                untracked.append(filepath)
            else:
                if index_status in ("A", "M", "D", "R", "C"):
                    staged.append(filepath)
                if worktree_status in ("M", "D"):
                    modified.append(filepath)

        clean = len(modified) == 0 and len(untracked) == 0 and len(staged) == 0

        return GitStatusResponse(
            branch=branch,
            clean=clean,
            modified=modified,
            untracked=untracked,
            staged=staged,
        )

    async def commit(self, message: str, files: Optional[list[str]] = None) -> str:
        """Commit changes and return commit hash."""
        if files:
            for f in files:
                _, stderr, rc = await self._run_git("add", f)
                if rc != 0:
                    raise RuntimeError(f"git add failed for {f}: {stderr}")
        else:
            _, stderr, rc = await self._run_git("add", "-A")
            if rc != 0:
                raise RuntimeError(f"git add -A failed: {stderr}")

        stdout, stderr, rc = await self._run_git("commit", "-m", message)
        if rc != 0:
            raise RuntimeError(f"git commit failed: {stderr}")

        # Get commit hash
        hash_out, _, _ = await self._run_git("rev-parse", "HEAD")
        return hash_out

    async def diff(self, staged: bool = False) -> GitDiffResponse:
        """Get diff output."""
        args = ["diff"]
        if staged:
            args.append("--cached")
        args.append("--stat")

        # Get stat summary
        stat_out, _, _ = await self._run_git(*args)

        # Get full diff
        diff_args = ["diff"]
        if staged:
            diff_args.append("--cached")
        diff_out, _, _ = await self._run_git(*diff_args)

        # Parse stat
        files_changed = 0
        insertions = 0
        deletions = 0

        if stat_out:
            # Last line of --stat has summary like: "2 files changed, 10 insertions(+), 3 deletions(-)"
            lines = stat_out.strip().splitlines()
            if lines:
                summary = lines[-1]
                files_match = re.search(r"(\d+) files? changed", summary)
                ins_match = re.search(r"(\d+) insertions?", summary)
                del_match = re.search(r"(\d+) deletions?", summary)
                if files_match:
                    files_changed = int(files_match.group(1))
                if ins_match:
                    insertions = int(ins_match.group(1))
                if del_match:
                    deletions = int(del_match.group(1))

        return GitDiffResponse(
            diff_text=diff_out,
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
        )

    async def log(self, limit: int = 20) -> list[dict]:
        """Get commit log."""
        stdout, stderr, rc = await self._run_git(
            "log", f"--max-count={limit}",
            "--format=%H|%an|%ae|%ai|%s",
        )
        if rc != 0:
            # Might be empty repo
            if "does not have any commits" in stderr or "bad default revision" in stderr:
                return []
            raise RuntimeError(f"git log failed: {stderr}")

        commits: list[dict] = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "author_name": parts[1],
                    "author_email": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                })
        return commits

    async def branch_current(self) -> str:
        """Get current branch name."""
        stdout, stderr, rc = await self._run_git("branch", "--show-current")
        if rc != 0 or not stdout:
            # Might be detached HEAD or no commits
            stdout, _, _ = await self._run_git("rev-parse", "--abbrev-ref", "HEAD")
            return stdout or "main"
        return stdout

    async def branch_list(self) -> list[str]:
        """List all local branches."""
        stdout, stderr, rc = await self._run_git("branch", "--list", "--format=%(refname:short)")
        if rc != 0:
            return []
        return [b.strip() for b in stdout.splitlines() if b.strip()]

    async def branch_create(self, name: str) -> None:
        """Create a new branch."""
        _, stderr, rc = await self._run_git("branch", name)
        if rc != 0:
            raise RuntimeError(f"git branch create failed: {stderr}")

    async def checkout(self, ref: str) -> None:
        """Checkout a branch or ref."""
        _, stderr, rc = await self._run_git("checkout", ref)
        if rc != 0:
            raise RuntimeError(f"git checkout failed: {stderr}")
