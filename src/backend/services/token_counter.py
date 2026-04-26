from backend.features.chat.schemas import ChatMessage


class TokenCounter:
    def count_text(self, text: str) -> int:
        # Model-agnostic approximation: 1 token ~= 4 chars.
        return max(1, len(text) // 4)

    def count_messages(self, messages: list[ChatMessage]) -> int:
        return sum(self.count_text(msg.content) for msg in messages)


token_counter = TokenCounter()
