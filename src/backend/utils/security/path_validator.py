"""
Shared path traversal prevention utility.
Used by: workspace, code_execution, mcp_server.
"""
import os
from pathlib import Path


class PathValidationError(Exception):
    """Raised when a path fails security validation."""
    pass


def validate_path_within_root(path: str, root: str) -> str:
    """
    Validate that a path resolves within the given root directory.
    Returns the resolved absolute path if valid.
    Raises PathValidationError if path escapes root.
    """
    if not path or not root:
        raise PathValidationError("Path and root must be non-empty")

    # Normalize and resolve
    root_resolved = os.path.realpath(root)
    
    # Join and resolve the target path
    if os.path.isabs(path):
        target = os.path.realpath(path)
    else:
        target = os.path.realpath(os.path.join(root_resolved, path))

    # Check containment
    if not target.startswith(root_resolved + os.sep) and target != root_resolved:
        raise PathValidationError(
            f"Path '{path}' resolves outside root directory"
        )

    return target


def is_safe_filename(filename: str) -> bool:
    """Check if a filename is safe (no path separators, no special files)."""
    if not filename or filename in ('.', '..'):
        return False
    if any(c in filename for c in ('/', '\\', '\x00')):
        return False
    if filename.startswith('.') and filename.count('.') == len(filename):
        return False
    return len(filename) <= 255
