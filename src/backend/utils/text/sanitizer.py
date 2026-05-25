"""
Shared input sanitization utility.
Used by: workspace, code_execution, mcp_server.
"""
import re
import unicodedata

_DANGEROUS_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_FILENAME_UNSAFE = re.compile(r'[<>:"/\\|?*\x00]')


def sanitize_text(text: str, max_length: int = 50000) -> str:
    """Remove control characters and limit length."""
    cleaned = _DANGEROUS_CHARS.sub('', text)
    return cleaned[:max_length]


def sanitize_filename(name: str) -> str:
    """Sanitize a filename - remove unsafe characters."""
    name = unicodedata.normalize('NFC', name.strip())
    name = _FILENAME_UNSAFE.sub('_', name)
    name = name.strip('. ')
    return name[:255] if name else 'unnamed'
