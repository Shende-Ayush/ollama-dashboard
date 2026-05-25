"""
Shared Fill-in-Middle (FIM) prompt formatting.
Used by: ai_coding (completion).
"""
from dataclasses import dataclass


@dataclass
class FIMPrompt:
    """Formatted FIM prompt ready for model input."""
    prompt: str
    stop_tokens: list[str]


# Model-specific FIM formats
FIM_FORMATS = {
    "codellama": {
        "prefix": "<PRE> ",
        "suffix": " <SUF>",
        "middle": " <MID>",
        "stop": ["<EOT>", "</s>"],
    },
    "deepseek": {
        "prefix": "<|fim▁begin|>",
        "suffix": "<|fim▁hole|>",
        "middle": "<|fim▁end|>",
        "stop": ["<|fim▁begin|>", "<|fim▁hole|>", "<|fim▁end|>", "<|end▁of▁sentence|>"],
    },
    "qwen": {
        "prefix": "<|fim_prefix|>",
        "suffix": "<|fim_suffix|>",
        "middle": "<|fim_middle|>",
        "stop": ["<|fim_prefix|>", "<|fim_suffix|>", "<|fim_middle|>", "<|endoftext|>"],
    },
    "starcoder": {
        "prefix": "<fim_prefix>",
        "suffix": "<fim_suffix>",
        "middle": "<fim_middle>",
        "stop": ["<fim_prefix>", "<fim_suffix>", "<fim_middle>", "<|endoftext|>"],
    },
}

# Default (generic) format
DEFAULT_FIM = {
    "prefix": "",
    "suffix": "",
    "middle": "",
    "stop": ["\n\n", "</s>"],
}


def detect_model_family(model_name: str) -> str:
    """Detect the model family from its name for FIM formatting."""
    name_lower = model_name.lower()
    if "codellama" in name_lower or "code-llama" in name_lower:
        return "codellama"
    if "deepseek" in name_lower:
        return "deepseek"
    if "qwen" in name_lower:
        return "qwen"
    if "starcoder" in name_lower or "star" in name_lower:
        return "starcoder"
    return "default"


def format_fim_prompt(
    prefix_code: str,
    suffix_code: str,
    model_name: str,
) -> FIMPrompt:
    """
    Format code into a Fill-in-Middle prompt for the given model.
    
    Args:
        prefix_code: Code before the cursor
        suffix_code: Code after the cursor
        model_name: Ollama model name (e.g., "deepseek-coder-v2:1.5b")
    
    Returns:
        FIMPrompt with formatted prompt string and stop tokens
    """
    family = detect_model_family(model_name)
    fmt = FIM_FORMATS.get(family, DEFAULT_FIM)

    if family == "default":
        # For models without FIM support, use instruction format
        prompt = (
            f"Complete the code at the cursor position marked with <CURSOR>.\n"
            f"Only output the completion, nothing else.\n\n"
            f"{prefix_code}<CURSOR>{suffix_code}"
        )
        return FIMPrompt(prompt=prompt, stop_tokens=fmt["stop"])

    prompt = f"{fmt['prefix']}{prefix_code}{fmt['suffix']}{suffix_code}{fmt['middle']}"
    return FIMPrompt(prompt=prompt, stop_tokens=fmt["stop"])
