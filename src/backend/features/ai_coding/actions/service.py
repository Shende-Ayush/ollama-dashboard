"""Code Actions — explain, refactor, optimize, fix, add_docs, add_tests."""
import logging
import time
from backend.features.ai_coding.schemas import CodeActionRequest, CodeActionResponse
from backend.services.model_provider.registry import model_registry
from backend.services.model_provider.base import GenerationOptions
from backend.utils.text.tokenizer import estimate_tokens

logger = logging.getLogger(__name__)

ACTION_PROMPTS = {
    "explain": "Explain the following {language} code concisely. Focus on what it does, not how.\n\n```{language}\n{code}\n```",
    "refactor": "Refactor the following {language} code for better readability and maintainability. Return ONLY the refactored code.\n\n```{language}\n{code}\n```",
    "optimize": "Optimize the following {language} code for performance. Return ONLY the optimized code with brief comments explaining changes.\n\n```{language}\n{code}\n```",
    "fix": "Fix any bugs in the following {language} code. Return ONLY the fixed code.\n\n```{language}\n{code}\n```",
    "add_docs": "Add comprehensive docstrings/comments to the following {language} code. Return the full code with documentation added.\n\n```{language}\n{code}\n```",
    "add_tests": "Write unit tests for the following {language} code. Use the standard testing framework for the language.\n\n```{language}\n{code}\n```",
}

class CodeActionService:
    """Execute code actions (explain, refactor, etc.)."""
    
    SUPPORTED_ACTIONS = list(ACTION_PROMPTS.keys())
    
    async def execute(self, request: CodeActionRequest) -> CodeActionResponse:
        """Execute a code action."""
        if request.action not in self.SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported action: {request.action}. Supported: {self.SUPPORTED_ACTIONS}")
        
        start_time = time.time()
        
        # Build prompt
        prompt_template = ACTION_PROMPTS[request.action]
        prompt = prompt_template.format(language=request.language, code=request.code)
        if request.context:
            prompt += f"\n\nAdditional context: {request.context}"
        
        # Select model
        provider = model_registry.get("ollama")
        try:
            available = await provider.list_models()
            model_name = request.model or (available[0].name if available else "llama3.2:3b")
        except Exception:
            model_name = request.model or "llama3.2:3b"
        
        # Generate
        result_text = ""
        try:
            options = GenerationOptions(temperature=0.3, max_tokens=4096)
            async for token in provider.chat_stream(
                model_name, 
                [{"role": "user", "content": prompt}],
                options,
            ):
                result_text += token
        except Exception as exc:
            logger.error("Code action failed: %s", exc)
            result_text = f"Error: {str(exc)}"
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return CodeActionResponse(
            result=result_text,
            action=request.action,
            model_used=model_name,
            tokens_used=estimate_tokens(prompt) + estimate_tokens(result_text),
            latency_ms=latency_ms,
        )

code_action_service = CodeActionService()
