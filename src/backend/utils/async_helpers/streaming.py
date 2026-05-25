"""
Shared SSE (Server-Sent Events) streaming helpers.
Used by: chat, code_execution, ai_coding, autonomous.
"""
import json
from typing import Any


def format_sse_event(data: dict[str, Any], event_type: str | None = None) -> str:
    """Format a dict as an SSE event string."""
    lines = []
    if event_type:
        lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


def format_sse_data(data: dict[str, Any]) -> str:
    """Format a dict as SSE data-only (no event type)."""
    return f"data: {json.dumps(data)}\n\n"


def format_sse_error(message: str, code: str = "error") -> str:
    """Format an error as SSE event."""
    return format_sse_event({"error": message, "code": code}, event_type="error")


def format_sse_done() -> str:
    """Format a done/complete SSE event."""
    return format_sse_event({"status": "done"}, event_type="done")
