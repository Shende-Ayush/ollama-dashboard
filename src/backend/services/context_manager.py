from backend.features.chat.schemas import ChatMessage
from backend.services.token_counter import token_counter


class ContextManager:
    def summarize_messages(self, messages: list[ChatMessage]) -> ChatMessage:
        joined = " ".join(msg.content for msg in messages)
        summary = joined[:500]
        return ChatMessage(role="system", content=f"Summary of earlier context: {summary}")

    def trim_messages(self, messages: list[ChatMessage], context_tokens: int) -> list[ChatMessage]:
        budget = context_tokens
        kept: list[ChatMessage] = []
        running = 0
        for msg in reversed(messages):
            msg_size = token_counter.count_text(msg.content)
            if running + msg_size > budget:
                break
            kept.append(msg)
            running += msg_size
        kept = list(reversed(kept))
        if len(kept) < len(messages):
            # Optional summarization fallback for trimmed context.
            kept = [self.summarize_messages(messages[:-len(kept) or None]), *kept]
        return kept


context_manager = ContextManager()
