"""
Shared JSON extraction from LLM output.
Used by: smart_commands, agents, ai_coding.
"""
import json
import re
from typing import Any


def extract_json(raw: str) -> dict[str, Any]:
    """
    Extract JSON from potentially messy LLM output.
    Tries: direct parse → JSON block extraction → code fence extraction.
    Returns empty dict if no valid JSON found.
    """
    # 1. Try direct parse
    try:
        return json.loads(raw.strip())
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Try extracting JSON object block
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        try:
            return json.loads(json_match.group())
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. Try code fence extraction
    code_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', raw)
    if code_match:
        try:
            return json.loads(code_match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # 4. Try JSON array
    array_match = re.search(r'\[[\s\S]*\]', raw)
    if array_match:
        try:
            result = json.loads(array_match.group())
            return {"items": result} if isinstance(result, list) else {}
        except (json.JSONDecodeError, ValueError):
            pass

    return {}


def extract_code_blocks(text: str) -> list[dict[str, str]]:
    """Extract code blocks from markdown-formatted text."""
    pattern = r'```(\w*)\n([\s\S]*?)```'
    blocks = []
    for match in re.finditer(pattern, text):
        blocks.append({
            "language": match.group(1) or "text",
            "code": match.group(2).strip(),
        })
    return blocks
