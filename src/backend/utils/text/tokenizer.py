"""
Shared token counting utility.
Used by: chat, ai_coding, prompt_studio, agents, rag_pipeline.
"""


def estimate_tokens(text: str) -> int:
    """Estimate token count using character-based heuristic (4 chars ≈ 1 token)."""
    if not text:
        return 1
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Estimate total tokens across a list of message dicts."""
    return sum(estimate_tokens(m.get("content", "")) for m in messages)
