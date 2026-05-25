"""
Workspace & File System — File operations service.

Provides secure file operations within a workspace root directory.
Uses asyncio.to_thread for non-blocking I/O.
"""
import asyncio
import hashlib
import os
from typing import Optional

from backend.features.workspace.schemas import FileNode, SearchResult
from backend.utils.security.path_validator import PathValidationError, validate_path_within_root


# Language detection by file extension
_EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
    ".xml": "xml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".txt": "text",
    ".dockerfile": "dockerfile",
    ".env": "dotenv",
}


def _detect_language(file_path: str) -> Optional[str]:
    """Detect language from file extension."""
    name = os.path.basename(file_path).lower()
    if name == "dockerfile":
        return "dockerfile"
    if name == "makefile":
        return "makefile"
    ext = os.path.splitext(name)[1]
    return _EXTENSION_LANGUAGE_MAP.get(ext)


class FileSystemService:
    """File operations within a workspace root directory."""

    def __init__(self, root_path: str):
        self.root = root_path

    def _resolve(self, path: str) -> str:
        """Resolve path within root, raise if escape attempt."""
        if not path or path == "":
            return os.path.realpath(self.root)
        return validate_path_within_root(path, self.root)

    async def read_file(self, path: str) -> str:
        """Read file content as text."""
        resolved = self._resolve(path)

        def _read():
            if not os.path.isfile(resolved):
                raise FileNotFoundError(f"File not found: {path}")
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

        return await asyncio.to_thread(_read)

    async def write_file(self, path: str, content: str) -> None:
        """Write content to a file, creating parent directories as needed."""
        resolved = self._resolve(path)

        def _write():
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)

        await asyncio.to_thread(_write)

    async def delete_file(self, path: str) -> None:
        """Delete a file or empty directory."""
        resolved = self._resolve(path)

        def _delete():
            if not os.path.exists(resolved):
                raise FileNotFoundError(f"Path not found: {path}")
            if os.path.isdir(resolved):
                os.rmdir(resolved)
            else:
                os.remove(resolved)

        await asyncio.to_thread(_delete)

    async def create_directory(self, path: str) -> None:
        """Create a directory (and parents)."""
        resolved = self._resolve(path)
        await asyncio.to_thread(os.makedirs, resolved, exist_ok=True)

    async def list_tree(self, path: str = "") -> list[FileNode]:
        """List directory contents as a tree structure."""
        resolved = self._resolve(path) if path else os.path.realpath(self.root)

        def _list():
            if not os.path.isdir(resolved):
                raise FileNotFoundError(f"Directory not found: {path}")
            
            nodes: list[FileNode] = []
            try:
                entries = sorted(os.listdir(resolved))
            except PermissionError:
                return nodes

            for entry in entries:
                # Skip hidden files/dirs
                if entry.startswith("."):
                    continue
                full_path = os.path.join(resolved, entry)
                rel_path = os.path.relpath(full_path, self.root)
                is_dir = os.path.isdir(full_path)
                size = 0 if is_dir else os.path.getsize(full_path)
                lang = None if is_dir else _detect_language(entry)

                node = FileNode(
                    name=entry,
                    path=rel_path,
                    is_directory=is_dir,
                    size_bytes=size,
                    language=lang,
                    children=[] if is_dir else None,
                )
                nodes.append(node)
            return nodes

        return await asyncio.to_thread(_list)

    async def search(self, query: str, include_content: bool = False) -> list[SearchResult]:
        """Search for files matching query (filename or content search)."""

        def _search():
            results: list[SearchResult] = []
            query_lower = query.lower()

            for root_dir, dirs, files in os.walk(self.root):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for filename in files:
                    if filename.startswith("."):
                        continue
                    full_path = os.path.join(root_dir, filename)
                    rel_path = os.path.relpath(full_path, self.root)
                    lang = _detect_language(filename)

                    # Filename match
                    if query_lower in filename.lower():
                        results.append(SearchResult(
                            path=rel_path,
                            line_number=None,
                            match_text=filename,
                            language=lang,
                        ))

                    # Content search
                    if include_content:
                        try:
                            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                                for line_num, line in enumerate(f, 1):
                                    if query_lower in line.lower():
                                        results.append(SearchResult(
                                            path=rel_path,
                                            line_number=line_num,
                                            match_text=line.rstrip()[:200],
                                            language=lang,
                                        ))
                                        if len(results) >= 100:
                                            return results
                        except (OSError, UnicodeDecodeError):
                            continue

                    if len(results) >= 100:
                        return results

            return results

        return await asyncio.to_thread(_search)

    async def file_exists(self, path: str) -> bool:
        """Check if a file or directory exists."""
        try:
            resolved = self._resolve(path)
            return await asyncio.to_thread(os.path.exists, resolved)
        except PathValidationError:
            return False

    async def get_file_info(self, path: str) -> dict:
        """Get file metadata."""
        resolved = self._resolve(path)

        def _info():
            if not os.path.exists(resolved):
                raise FileNotFoundError(f"Path not found: {path}")
            stat = os.stat(resolved)
            is_dir = os.path.isdir(resolved)
            content_hash = None
            if not is_dir:
                with open(resolved, "rb") as f:
                    content_hash = hashlib.sha256(f.read()).hexdigest()
            return {
                "path": os.path.relpath(resolved, self.root),
                "is_directory": is_dir,
                "size_bytes": stat.st_size if not is_dir else 0,
                "language": _detect_language(resolved) if not is_dir else None,
                "content_hash": content_hash,
            }

        return await asyncio.to_thread(_info)
