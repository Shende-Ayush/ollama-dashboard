"""Build optimal context for code completion."""
from backend.utils.text.tokenizer import estimate_tokens

class ContextBuilder:
    """Builds context window for FIM completion."""
    
    DEFAULT_MAX_CONTEXT = 2048  # tokens
    
    def build_context(self, prefix: str, suffix: str, max_tokens: int = 2048) -> tuple[str, str]:
        """Trim prefix/suffix to fit within token budget.
        
        Strategy: Keep the end of prefix (nearest to cursor) and start of suffix.
        Allocate 70% to prefix, 30% to suffix.
        """
        prefix_budget = int(max_tokens * 0.7)
        suffix_budget = max_tokens - prefix_budget
        
        # Trim prefix from the beginning if too long
        prefix_tokens = estimate_tokens(prefix)
        if prefix_tokens > prefix_budget:
            # Keep last N characters (approximate)
            chars_to_keep = prefix_budget * 4  # 4 chars per token approx
            prefix = prefix[-chars_to_keep:]
        
        # Trim suffix from the end if too long
        suffix_tokens = estimate_tokens(suffix)
        if suffix_tokens > suffix_budget:
            chars_to_keep = suffix_budget * 4
            suffix = suffix[:chars_to_keep]
        
        return prefix, suffix

context_builder = ContextBuilder()
