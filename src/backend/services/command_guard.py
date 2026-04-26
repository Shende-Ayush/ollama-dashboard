"""
Command guard — strict Ollama-only allowlist with safe argument validation.
No shell injection, no arbitrary execution.
"""
import re
import shlex

# Exact commands allowed (no args)
EXACT_ALLOWED = {
    "ollama ps",
    "ollama list",
    "ollama version",
}

# Commands that accept a single model-name arg
MODEL_ARG_COMMANDS = {
    "ollama run",
    "ollama pull",
    "ollama show",
    "ollama rm",
    "ollama push",
    "ollama cp",
}

# Safe model name pattern: letters, digits, dash, underscore, colon, dot, slash
_MODEL_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-:./]+$')

SHELL_INJECTION_TOKENS = ("&&", "||", "|", ";", ">", "<", "`", "$(", "${", "\n", "\r")


def validate_command(command: str) -> bool:
    """Return True if command is safe to execute, False otherwise."""
    cmd = command.strip()

    # Reject shell injection attempts
    if any(token in cmd for token in SHELL_INJECTION_TOKENS):
        return False

    # Exact match
    if cmd in EXACT_ALLOWED:
        return True

    # Parse safely
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return False

    if len(parts) < 2:
        return False

    prefix = f"{parts[0]} {parts[1]}"
    if prefix not in MODEL_ARG_COMMANDS:
        return False

    # Must have at most one model-name argument
    if len(parts) > 3:
        return False

    if len(parts) == 3:
        model_arg = parts[2]
        if not _MODEL_NAME_RE.match(model_arg):
            return False

    return True
