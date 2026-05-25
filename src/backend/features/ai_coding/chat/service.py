"""Editor AI Chat — conversational coding with file context."""
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.features.ai_coding.chat.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
)
from backend.services.model_provider.base import GenerationOptions
from backend.services.model_provider.registry import model_registry
from backend.utils.text.tokenizer import estimate_tokens

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI coding assistant integrated into a code editor.
When asked to modify code, respond with the complete modified code inside a fenced code block.
When explaining code, be concise and focused.
Always specify the language in code fences (e.g., ```python).
If changes span multiple files, clearly indicate each file path before its code block."""


class EditorChatService:
    """Handles AI chat with code context for the editor."""

    async def chat(self, request: ChatRequest, session: AsyncSession) -> ChatResponse:
        """Process a chat request with optional file context."""
        start_time = time.time()

        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add file context if provided
        if request.file_context:
            context_msg = self._build_context_message(request.file_context)
            messages.append({"role": "system", "content": context_msg})

        # Add conversation history
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        # Select model
        provider = model_registry.get("ollama")
        try:
            available = await provider.list_models()
            model_name = request.model or (available[0].name if available else "llama3.2:3b")
        except Exception:
            model_name = request.model or "llama3.2:3b"

        # Generate response
        response_text = ""
        try:
            options = GenerationOptions(
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                num_ctx=request.context_window,
            )
            async for token in provider.chat_stream(model_name, messages, options):
                response_text += token
        except Exception as exc:
            logger.error("Chat generation failed: %s", exc)
            response_text = f"Error: Failed to generate response. {str(exc)}"

        latency_ms = int((time.time() - start_time) * 1000)
        tokens_used = estimate_tokens(response_text)

        return ChatResponse(
            response=response_text,
            model_used=model_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            has_code_blocks=("```" in response_text),
        )

    def _build_context_message(self, file_context: list[dict]) -> str:
        """Build a context message from file references."""
        parts = ["The user is working with the following files:"]
        for ctx in file_context:
            path = ctx.get("path", "unknown")
            content = ctx.get("content", "")
            language = ctx.get("language", "")
            if content:
                parts.append(f"\n--- {path} ---\n```{language}\n{content}\n```")
            else:
                parts.append(f"\n- {path} (no content provided)")
        return "\n".join(parts)


editor_chat_service = EditorChatService()
