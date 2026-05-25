"""Route completion requests to optimal model."""

# Priority order per language (try first available)
COMPLETION_MODELS = {
    "python": ["deepseek-coder-v2:1.5b", "qwen2.5-coder:3b", "codellama:7b", "llama3.2:3b"],
    "javascript": ["qwen2.5-coder:3b", "deepseek-coder-v2:1.5b", "codellama:7b", "llama3.2:3b"],
    "typescript": ["qwen2.5-coder:3b", "deepseek-coder-v2:1.5b", "codellama:7b", "llama3.2:3b"],
    "go": ["deepseek-coder-v2:1.5b", "qwen2.5-coder:3b", "codellama:7b"],
    "rust": ["deepseek-coder-v2:1.5b", "qwen2.5-coder:3b", "codellama:7b"],
    "default": ["llama3.2:3b", "mistral:7b", "qwen2.5:7b"],
}

# Models known to support FIM natively
FIM_CAPABLE_MODELS = {
    "deepseek-coder", "qwen2.5-coder", "codellama", "starcoder", 
    "codegemma", "stable-code",
}

class ModelRouter:
    """Select the best available model for a completion request."""
    
    def select_model(self, language: str, available_models: list[str], override: str | None = None) -> str:
        """Pick the best model for the given language.
        
        Args:
            language: Programming language
            available_models: Currently installed models
            override: User-specified model override
        
        Returns:
            Model name to use
        """
        if override and override in available_models:
            return override
        
        # Get preferred models for language
        preferred = COMPLETION_MODELS.get(language.lower(), COMPLETION_MODELS["default"])
        
        # Find first available from preferred list
        available_set = set(available_models)
        for model in preferred:
            if model in available_set:
                return model
        
        # Fallback: any FIM-capable model
        for model in available_models:
            model_base = model.split(":")[0].lower()
            if any(fim in model_base for fim in FIM_CAPABLE_MODELS):
                return model
        
        # Last resort: first available model
        if available_models:
            return available_models[0]
        
        return "llama3.2:3b"  # Default fallback
    
    def supports_fim(self, model_name: str) -> bool:
        """Check if model supports native FIM."""
        model_base = model_name.split(":")[0].lower()
        return any(fim in model_base for fim in FIM_CAPABLE_MODELS)

model_router = ModelRouter()
