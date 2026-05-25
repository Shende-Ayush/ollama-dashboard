"""
Tests for Sprint 4: AI Code Completion Engine.

Tests cover:
1. CompletionCache - get/put, TTL expiry, LRU eviction, hit rate tracking
2. ContextBuilder - prefix/suffix trimming, budget allocation
3. ModelRouter - language preference, FIM detection, fallback behavior
4. CodeActionService - supported actions list, unsupported action raises ValueError
5. API endpoint tests (mock provider to avoid real Ollama)
"""
import time
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.features.ai_coding.completion.cache import CompletionCache
from backend.features.ai_coding.completion.context_builder import ContextBuilder
from backend.features.ai_coding.completion.model_router import ModelRouter
from backend.features.ai_coding.actions.service import CodeActionService
from backend.features.ai_coding.schemas import (
    CodeActionRequest,
)


# ===========================================================================
# Unit Tests: CompletionCache
# ===========================================================================
class TestCompletionCache:
    """Tests for the LRU completion cache."""

    def test_put_and_get(self):
        """Cache stores and retrieves entries correctly."""
        cache = CompletionCache(max_size=10, ttl_seconds=60)
        cache.put("def foo():", "", "python", "    pass", "llama3.2:3b")
        
        entry = cache.get("def foo():", "", "python")
        assert entry is not None
        assert entry.completion == "    pass"
        assert entry.model == "llama3.2:3b"

    def test_cache_miss(self):
        """Cache returns None for missing entries."""
        cache = CompletionCache(max_size=10, ttl_seconds=60)
        entry = cache.get("not in cache", "", "python")
        assert entry is None

    def test_ttl_expiry(self):
        """Entries expire after TTL."""
        cache = CompletionCache(max_size=10, ttl_seconds=1)
        cache.put("prefix", "suffix", "python", "result", "model")
        
        # Manually expire the entry
        key = cache._make_key("prefix", "suffix", "python")
        cache._cache[key].timestamp = time.time() - 2  # 2 seconds ago
        
        entry = cache.get("prefix", "suffix", "python")
        assert entry is None

    def test_lru_eviction(self):
        """Oldest entries are evicted when cache is full."""
        cache = CompletionCache(max_size=3, ttl_seconds=60)
        
        # Fill cache
        cache.put("p1", "s1", "python", "r1", "m1")
        cache.put("p2", "s2", "python", "r2", "m2")
        cache.put("p3", "s3", "python", "r3", "m3")
        
        # This should evict the first entry
        cache.put("p4", "s4", "python", "r4", "m4")
        
        assert cache.get("p1", "s1", "python") is None
        assert cache.get("p4", "s4", "python") is not None
        assert len(cache._cache) == 3

    def test_hit_rate_tracking(self):
        """Hit rate is correctly calculated."""
        cache = CompletionCache(max_size=10, ttl_seconds=60)
        cache.put("prefix", "suffix", "python", "result", "model")
        
        # 1 hit
        cache.get("prefix", "suffix", "python")
        # 1 miss
        cache.get("other", "other", "python")
        
        assert cache._hits == 1
        assert cache._misses == 1
        assert cache.hit_rate == 0.5

    def test_stats_property(self):
        """Stats property returns correct info."""
        cache = CompletionCache(max_size=100, ttl_seconds=60)
        cache.put("p", "s", "python", "r", "m")
        cache.get("p", "s", "python")  # hit
        cache.get("x", "y", "python")  # miss
        
        stats = cache.stats
        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0

    def test_lru_access_updates_order(self):
        """Accessing an entry moves it to the end (most recently used)."""
        cache = CompletionCache(max_size=3, ttl_seconds=60)
        
        cache.put("p1", "s1", "python", "r1", "m1")
        cache.put("p2", "s2", "python", "r2", "m2")
        cache.put("p3", "s3", "python", "r3", "m3")
        
        # Access p1, making it recently used
        cache.get("p1", "s1", "python")
        
        # Add new entry - should evict p2 (least recently used)
        cache.put("p4", "s4", "python", "r4", "m4")
        
        assert cache.get("p2", "s2", "python") is None
        # p1 should still be there since we accessed it
        assert cache.get("p1", "s1", "python") is not None


# ===========================================================================
# Unit Tests: ContextBuilder
# ===========================================================================
class TestContextBuilder:
    """Tests for the context builder."""

    def test_short_context_unchanged(self):
        """Short prefix/suffix are returned unchanged."""
        builder = ContextBuilder()
        prefix = "def foo():\n"
        suffix = "\nprint('done')"
        
        result_prefix, result_suffix = builder.build_context(prefix, suffix, max_tokens=2048)
        assert result_prefix == prefix
        assert result_suffix == suffix

    def test_long_prefix_trimmed(self):
        """Long prefix is trimmed from the beginning."""
        builder = ContextBuilder()
        prefix = "x" * 20000  # Very long prefix
        suffix = "y" * 100
        
        result_prefix, result_suffix = builder.build_context(prefix, suffix, max_tokens=100)
        
        # Prefix should be shorter than original
        assert len(result_prefix) < len(prefix)
        # Should keep the end of prefix
        assert result_prefix == prefix[-int(100 * 0.7) * 4:]

    def test_long_suffix_trimmed(self):
        """Long suffix is trimmed from the end."""
        builder = ContextBuilder()
        prefix = "x" * 100
        suffix = "y" * 20000  # Very long suffix
        
        result_prefix, result_suffix = builder.build_context(prefix, suffix, max_tokens=100)
        
        # Suffix should be shorter than original
        assert len(result_suffix) < len(suffix)
        # Should keep the start of suffix
        assert result_suffix == suffix[:int(100 * 0.3) * 4]

    def test_budget_allocation_70_30(self):
        """Budget is split 70% prefix, 30% suffix."""
        builder = ContextBuilder()
        prefix = "a" * 50000
        suffix = "b" * 50000
        
        result_prefix, result_suffix = builder.build_context(prefix, suffix, max_tokens=1000)
        
        # Prefix budget = 700 tokens * 4 chars = 2800 chars
        # Suffix budget = 300 tokens * 4 chars = 1200 chars
        assert len(result_prefix) == 700 * 4
        assert len(result_suffix) == 300 * 4


# ===========================================================================
# Unit Tests: ModelRouter
# ===========================================================================
class TestModelRouter:
    """Tests for the model router."""

    def test_select_preferred_for_python(self):
        """Selects preferred model for Python."""
        router = ModelRouter()
        available = ["llama3.2:3b", "deepseek-coder-v2:1.5b", "mistral:7b"]
        result = router.select_model("python", available)
        assert result == "deepseek-coder-v2:1.5b"

    def test_select_preferred_for_javascript(self):
        """Selects preferred model for JavaScript."""
        router = ModelRouter()
        available = ["qwen2.5-coder:3b", "llama3.2:3b"]
        result = router.select_model("javascript", available)
        assert result == "qwen2.5-coder:3b"

    def test_override_takes_precedence(self):
        """User override is used when model is available."""
        router = ModelRouter()
        available = ["llama3.2:3b", "deepseek-coder-v2:1.5b", "mistral:7b"]
        result = router.select_model("python", available, override="mistral:7b")
        assert result == "mistral:7b"

    def test_override_ignored_if_unavailable(self):
        """Override is ignored if model is not available."""
        router = ModelRouter()
        available = ["llama3.2:3b", "deepseek-coder-v2:1.5b"]
        result = router.select_model("python", available, override="nonexistent:7b")
        assert result == "deepseek-coder-v2:1.5b"

    def test_fallback_to_fim_capable(self):
        """Falls back to FIM-capable model when no preferred is available."""
        router = ModelRouter()
        available = ["some-random:7b", "starcoder:7b"]
        result = router.select_model("python", available)
        assert result == "starcoder:7b"

    def test_fallback_to_first_available(self):
        """Falls back to first available model as last resort."""
        router = ModelRouter()
        available = ["some-random:7b", "another:13b"]
        result = router.select_model("python", available)
        assert result == "some-random:7b"

    def test_fallback_when_no_models(self):
        """Returns default fallback when no models available."""
        router = ModelRouter()
        result = router.select_model("python", [])
        assert result == "llama3.2:3b"

    def test_supports_fim_positive(self):
        """Correctly identifies FIM-capable models."""
        router = ModelRouter()
        assert router.supports_fim("deepseek-coder-v2:1.5b") is True
        assert router.supports_fim("codellama:7b") is True
        assert router.supports_fim("qwen2.5-coder:3b") is True
        assert router.supports_fim("starcoder:7b") is True

    def test_supports_fim_negative(self):
        """Correctly identifies non-FIM models."""
        router = ModelRouter()
        assert router.supports_fim("llama3.2:3b") is False
        assert router.supports_fim("mistral:7b") is False

    def test_unknown_language_uses_default(self):
        """Unknown languages use the default model list."""
        router = ModelRouter()
        available = ["llama3.2:3b", "mistral:7b"]
        result = router.select_model("cobol", available)
        assert result == "llama3.2:3b"


# ===========================================================================
# Unit Tests: CodeActionService
# ===========================================================================
class TestCodeActionService:
    """Tests for the code action service."""

    def test_supported_actions_list(self):
        """Service defines all expected actions."""
        service = CodeActionService()
        expected = ["explain", "refactor", "optimize", "fix", "add_docs", "add_tests"]
        assert service.SUPPORTED_ACTIONS == expected

    @pytest.mark.asyncio
    async def test_unsupported_action_raises(self):
        """Unsupported action raises ValueError."""
        service = CodeActionService()
        request = CodeActionRequest(
            code="print('hello')",
            action="invalid_action",
            language="python",
        )
        with pytest.raises(ValueError, match="Unsupported action"):
            await service.execute(request)

    @pytest.mark.asyncio
    async def test_execute_returns_response(self):
        """Execute returns a valid CodeActionResponse."""
        service = CodeActionService()
        request = CodeActionRequest(
            code="def add(a, b): return a + b",
            action="explain",
            language="python",
        )
        
        # Mock the provider
        async def mock_stream(*args, **kwargs):
            yield "This function adds two numbers."
        
        mock_model = MagicMock()
        mock_model.name = "llama3.2:3b"
        
        mock_provider = MagicMock()
        mock_provider.list_models = AsyncMock(return_value=[mock_model])
        mock_provider.chat_stream = MagicMock(return_value=mock_stream())
        
        with patch(
            "backend.features.ai_coding.actions.service.model_registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_provider
            result = await service.execute(request)
        
        assert result.action == "explain"
        assert result.result == "This function adds two numbers."
        assert result.latency_ms >= 0


# ===========================================================================
# API Endpoint Tests
# ===========================================================================

# Helper to create a mock async generator
async def mock_generate_stream(*args, **kwargs):
    yield "completed_code"


async def mock_chat_stream(*args, **kwargs):
    yield "Explanation of the code."


@pytest_asyncio.fixture
async def ai_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with AI coding router included."""
    from backend.main import app
    from backend.api.routes.ai_coding import router as ai_coding_router
    from backend.common.db.session import get_db_session

    # Include the AI coding router for tests
    app.include_router(ai_coding_router, prefix="/api")
    
    from tests.conftest import override_get_db_session
    app.dependency_overrides[get_db_session] = override_get_db_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


class TestAICodingAPI:
    """API endpoint tests for AI coding."""

    @pytest.mark.asyncio
    async def test_complete_code_endpoint(self, ai_client):
        """POST /api/ai-coding/complete returns completion."""
        mock_model = MagicMock()
        mock_model.name = "llama3.2:3b"
        mock_model.size_bytes = 2_000_000_000
        mock_model.family = "llama"
        
        mock_provider = MagicMock()
        mock_provider.list_models = AsyncMock(return_value=[mock_model])
        mock_provider.generate_stream = MagicMock(return_value=mock_generate_stream())
        
        with patch(
            "backend.features.ai_coding.completion.service.model_registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_provider
            
            response = await ai_client.post("/api/ai-coding/complete", json={
                "prefix": "def hello():\n    ",
                "suffix": "\n\nprint('done')",
                "language": "python",
                "max_tokens": 128,
            })
        
        assert response.status_code == 200
        data = response.json()
        assert "completion" in data
        assert "model_used" in data
        assert "tokens_generated" in data
        assert "latency_ms" in data
        assert data["completion"] == "completed_code"

    @pytest.mark.asyncio
    async def test_code_action_endpoint(self, ai_client):
        """POST /api/ai-coding/code-action returns action result."""
        mock_model = MagicMock()
        mock_model.name = "llama3.2:3b"
        
        mock_provider = MagicMock()
        mock_provider.list_models = AsyncMock(return_value=[mock_model])
        mock_provider.chat_stream = MagicMock(return_value=mock_chat_stream())
        
        with patch(
            "backend.features.ai_coding.actions.service.model_registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_provider
            
            response = await ai_client.post("/api/ai-coding/code-action", json={
                "code": "def add(a, b): return a + b",
                "action": "explain",
                "language": "python",
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "explain"
        assert data["result"] == "Explanation of the code."
        assert "model_used" in data
        assert "latency_ms" in data

    @pytest.mark.asyncio
    async def test_code_action_invalid_action(self, ai_client):
        """POST /api/ai-coding/code-action with invalid action returns 400."""
        response = await ai_client.post("/api/ai-coding/code-action", json={
            "code": "print('hello')",
            "action": "fly_to_moon",
            "language": "python",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_cache_stats_endpoint(self, ai_client):
        """GET /api/ai-coding/cache/stats returns stats."""
        response = await ai_client.get("/api/ai-coding/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert "size" in data
        assert "max_size" in data
        assert "hits" in data
        assert "misses" in data
        assert "hit_rate" in data

    @pytest.mark.asyncio
    async def test_cache_clear_endpoint(self, ai_client):
        """POST /api/ai-coding/cache/clear clears the cache."""
        response = await ai_client.post("/api/ai-coding/cache/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleared"

    @pytest.mark.asyncio
    async def test_complete_code_validation(self, ai_client):
        """POST /api/ai-coding/complete validates required fields."""
        # Missing prefix and language
        response = await ai_client.post("/api/ai-coding/complete", json={
            "suffix": "some code",
        })
        assert response.status_code == 422  # Validation error
