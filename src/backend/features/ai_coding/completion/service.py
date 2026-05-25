"""AI Code Completion — main service."""
import logging
import time
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.features.ai_coding.completion.cache import completion_cache
from backend.features.ai_coding.completion.context_builder import context_builder
from backend.features.ai_coding.completion.model_router import model_router
from backend.features.ai_coding.models import CompletionLog
from backend.features.ai_coding.schemas import CompletionRequest, CompletionResponse
from backend.services.model_provider.registry import model_registry
from backend.utils.ml.fim import format_fim_prompt
from backend.utils.text.tokenizer import estimate_tokens

logger = logging.getLogger(__name__)


class CompletionService:
    """Handles AI code completion requests."""

    async def complete(
        self, request: CompletionRequest, session: AsyncSession
    ) -> CompletionResponse:
        """Generate a code completion.
        
        Flow:
        1. Check cache
        2. Build context (trim to fit budget)
        3. Route to best model
        4. Format FIM prompt
        5. Generate completion
        6. Cache result
        7. Log to DB
        8. Return response
        """
        start_time = time.time()
        
        # 1. Check cache
        cached = completion_cache.get(request.prefix, request.suffix, request.language)
        if cached:
            latency_ms = int((time.time() - start_time) * 1000)
            await self._log_completion(
                request, cached.completion, cached.model, latency_ms, True, session
            )
            return CompletionResponse(
                completion=cached.completion,
                model_used=cached.model,
                tokens_generated=estimate_tokens(cached.completion),
                latency_ms=latency_ms,
                cache_hit=True,
            )
        
        # 2. Build context
        prefix, suffix = context_builder.build_context(
            request.prefix, request.suffix, max_tokens=2048
        )
        
        # 3. Select model
        provider = model_registry.get("ollama")
        try:
            available = await provider.list_models()
            available_names = [m.name for m in available]
        except Exception:
            available_names = ["llama3.2:3b"]
        
        model_name = model_router.select_model(
            request.language, available_names, request.model
        )
        
        # 4. Format FIM prompt
        fim = format_fim_prompt(prefix, suffix, model_name)
        
        # 5. Generate completion
        completion_text = ""
        try:
            from backend.services.model_provider.base import GenerationOptions
            options = GenerationOptions(
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stop=fim.stop_tokens + request.stop,
            )
            async for token in provider.generate_stream(model_name, fim.prompt, options):
                completion_text += token
                if len(completion_text) > request.max_tokens * 4:  # Safety: ~4 chars/token
                    break
        except Exception as exc:
            logger.error("Completion generation failed: %s", exc)
            latency_ms = int((time.time() - start_time) * 1000)
            return CompletionResponse(
                completion="",
                model_used=model_name,
                tokens_generated=0,
                latency_ms=latency_ms,
                finish_reason="error",
            )
        
        # Clean up completion (remove FIM artifacts)
        completion_text = self._clean_completion(completion_text)
        
        # 6. Cache result
        if completion_text:
            completion_cache.put(prefix, suffix, request.language, completion_text, model_name)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # 7. Log
        await self._log_completion(
            request, completion_text, model_name, latency_ms, False, session
        )
        
        # 8. Return
        finish_reason = "stop" if completion_text else "length"
        return CompletionResponse(
            completion=completion_text,
            model_used=model_name,
            tokens_generated=estimate_tokens(completion_text),
            latency_ms=latency_ms,
            cache_hit=False,
            finish_reason=finish_reason,
        )
    
    def _clean_completion(self, text: str) -> str:
        """Remove FIM special tokens and trailing artifacts."""
        # Common FIM end tokens
        stop_markers = [
            "<|fim", "<|end", "</s>", "<EOT>", "<|im_end|>",
            "\n\n\n", "```",
        ]
        for marker in stop_markers:
            if marker in text:
                text = text[:text.index(marker)]
        return text.rstrip()
    
    async def _log_completion(
        self,
        request: CompletionRequest,
        completion: str,
        model: str,
        latency_ms: int,
        cache_hit: bool,
        session: AsyncSession,
    ) -> None:
        """Log completion to database."""
        try:
            log = CompletionLog(
                workspace_id=uuid.UUID(request.workspace_id) if request.workspace_id else None,
                file_path=request.file_path,
                language=request.language,
                model_name=model,
                prompt_tokens=estimate_tokens(request.prefix + request.suffix),
                completion_tokens=estimate_tokens(completion),
                completion_text=completion[:500],  # Truncate for storage
                latency_ms=latency_ms,
                cache_hit=cache_hit,
            )
            session.add(log)
            await session.commit()
        except Exception as exc:
            logger.debug("Failed to log completion: %s", exc)


completion_service = CompletionService()
