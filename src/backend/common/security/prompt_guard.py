from fastapi import HTTPException, status


PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "reveal system prompt",
    "execute shell",
    "run arbitrary command",
)


def validate_prompt_content(text: str) -> None:
    lowered = text.lower()
    if any(pattern in lowered for pattern in PROMPT_INJECTION_PATTERNS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt rejected by safety policy")
