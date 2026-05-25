"""
Feature flags for progressive rollout.
Allows enabling/disabling features at runtime.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class FeatureFlags(BaseSettings):
    """Feature flags loaded from environment variables."""
    
    # Phase 2 features
    code_execution_enabled: bool = True
    workspace_enabled: bool = True
    ai_completion_enabled: bool = True
    ai_chat_enabled: bool = True
    autonomous_mode_enabled: bool = False
    mcp_server_enabled: bool = False
    rag_pipeline_enabled: bool = False
    arena_mode_enabled: bool = False
    
    class Config:
        env_prefix = "FF_"
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_feature_flags() -> FeatureFlags:
    return FeatureFlags()


def is_enabled(flag_name: str) -> bool:
    """Check if a feature flag is enabled."""
    flags = get_feature_flags()
    return getattr(flags, flag_name, False)
