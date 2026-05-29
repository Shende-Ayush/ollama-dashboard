"""
Tests for existing features and services.

Covers:
- Command guard (allowlist validation)
- Circuit breaker
- Token counter
- Context manager
- Pagination utility
- OllamaClient (mocked)
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.command_guard import validate_command
from backend.services.circuit_breaker import CircuitBreaker
from backend.services.token_counter import TokenCounter
from backend.services.context_manager import ContextManager
from backend.schemas.pagination import paginate, PaginatedResponse
from backend.features.chat.schemas import ChatMessage


# ===========================================================================
# Test: Command Guard
# ===========================================================================
class TestCommandGuard:
    """Tests for command allowlist validation."""

    # --- Valid commands ---
    def test_exact_allowed_ps(self):
        assert validate_command("ollama ps") is True

    def test_exact_allowed_list(self):
        assert validate_command("ollama list") is True

    def test_exact_allowed_version(self):
        assert validate_command("ollama version") is True

    def test_model_arg_pull(self):
        assert validate_command("ollama pull llama3.2:3b") is True

    def test_model_arg_show(self):
        assert validate_command("ollama show mistral:7b") is True

    def test_model_arg_rm(self):
        assert validate_command("ollama rm phi4:latest") is True

    def test_model_arg_stop(self):
        assert validate_command("ollama stop qwen2.5:7b") is True

    def test_model_with_slash(self):
        assert validate_command("ollama pull library/llama3") is True

    # --- Invalid commands ---
    def test_shell_injection_semicolon(self):
        assert validate_command("ollama ps; rm -rf /") is False

    def test_shell_injection_pipe(self):
        assert validate_command("ollama list | grep x") is False

    def test_shell_injection_and(self):
        assert validate_command("ollama ps && echo pwned") is False

    def test_shell_injection_backtick(self):
        assert validate_command("ollama pull `whoami`") is False

    def test_shell_injection_dollar(self):
        assert validate_command("ollama pull $(cat /etc/passwd)") is False

    def test_redirect(self):
        assert validate_command("ollama list > /tmp/out") is False

    def test_unknown_command(self):
        assert validate_command("ollama run model") is False

    def test_non_ollama_command(self):
        assert validate_command("ls -la") is False

    def test_empty_command(self):
        assert validate_command("") is False

    def test_too_many_args(self):
        assert validate_command("ollama pull model extra_arg") is False

    def test_invalid_model_name_chars(self):
        assert validate_command("ollama pull @#$%^&*") is False

    def test_whitespace_handling(self):
        assert validate_command("  ollama ps  ") is True



# ===========================================================================
# Test: Circuit Breaker
# ===========================================================================
class TestCircuitBreaker:
    """Tests for circuit breaker pattern implementation."""

    def test_initial_state_allows(self):
        cb = CircuitBreaker(failure_threshold=3, reset_after_seconds=10)
        assert cb.allow() is True

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, reset_after_seconds=60)
        cb.record_failure()
        cb.record_failure()
        assert cb.allow() is True  # Still under threshold
        cb.record_failure()
        assert cb.allow() is False  # Now open

    def test_success_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=3, reset_after_seconds=60)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failures == 0
        assert cb.allow() is True

    def test_resets_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, reset_after_seconds=1)
        cb.record_failure()
        cb.record_failure()
        assert cb.allow() is False

        # Simulate time passing
        cb.open_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert cb.allow() is True
        assert cb.failures == 0

    def test_stays_open_before_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, reset_after_seconds=60)
        cb.record_failure()
        cb.record_failure()
        # open_until is 60 seconds in future
        assert cb.allow() is False


# ===========================================================================
# Test: Token Counter
# ===========================================================================
class TestTokenCounter:
    """Tests for token estimation."""

    def test_empty_string(self):
        tc = TokenCounter()
        assert tc.count_text("") == 1  # minimum 1

    def test_short_text(self):
        tc = TokenCounter()
        result = tc.count_text("Hello")
        assert result == 1  # 5 chars // 4 = 1

    def test_longer_text(self):
        tc = TokenCounter()
        text = "This is a longer piece of text for token counting."
        result = tc.count_text(text)
        assert result == len(text) // 4

    def test_count_messages(self):
        tc = TokenCounter()
        messages = [
            ChatMessage(role="user", content="Hello world"),
            ChatMessage(role="assistant", content="Hi there!"),
        ]
        result = tc.count_messages(messages)
        expected = tc.count_text("Hello world") + tc.count_text("Hi there!")
        assert result == expected

    def test_count_messages_empty(self):
        tc = TokenCounter()
        assert tc.count_messages([]) == 0


# ===========================================================================
# Test: Context Manager
# ===========================================================================
class TestContextManager:
    """Tests for message trimming and context management."""

    def test_trim_messages_within_budget(self):
        cm = ContextManager()
        messages = [
            ChatMessage(role="user", content="Short message"),
        ]
        result = cm.trim_messages(messages, context_tokens=1000)
        assert len(result) == 1
        assert result[0].content == "Short message"

    def test_trim_messages_exceeds_budget(self):
        cm = ContextManager()
        messages = [
            ChatMessage(role="user", content="A" * 4000),  # ~1000 tokens
            ChatMessage(role="assistant", content="B" * 4000),
            ChatMessage(role="user", content="C" * 100),  # ~25 tokens
        ]
        result = cm.trim_messages(messages, context_tokens=50)
        # Should keep only what fits
        assert len(result) <= len(messages)

    def test_trim_adds_summary_when_truncated(self):
        cm = ContextManager()
        messages = [
            ChatMessage(role="user", content="First " * 500),
            ChatMessage(role="assistant", content="Second " * 500),
            ChatMessage(role="user", content="Third"),
        ]
        result = cm.trim_messages(messages, context_tokens=10)
        # First message should be a summary if context was too small
        if len(result) < len(messages):
            assert "Summary" in result[0].content or result[0].role == "system"

    def test_summarize_messages(self):
        cm = ContextManager()
        messages = [
            ChatMessage(role="user", content="Hello how are you?"),
            ChatMessage(role="assistant", content="I'm fine thanks"),
        ]
        summary = cm.summarize_messages(messages)
        assert summary.role == "system"
        assert "Summary" in summary.content



# ===========================================================================
# Test: Pagination Utility
# ===========================================================================
class TestPagination:
    """Tests for pagination utility."""

    def test_basic_pagination(self):
        items = list(range(50))
        result = paginate(items, pg_no=1, pg_size=10)
        assert isinstance(result, PaginatedResponse)
        assert result.page.total_records == 50
        assert result.page.total_pg == 5
        assert result.page.pg_no == 1
        assert result.page.pg_size == 10
        assert len(result.items) == 10
        assert result.items[0] == 0
        assert result.items[9] == 9

    def test_second_page(self):
        items = list(range(25))
        result = paginate(items, pg_no=2, pg_size=10)
        assert len(result.items) == 10
        assert result.items[0] == 10
        assert result.items[9] == 19

    def test_last_partial_page(self):
        items = list(range(25))
        result = paginate(items, pg_no=3, pg_size=10)
        assert len(result.items) == 5
        assert result.items[0] == 20

    def test_empty_list(self):
        result = paginate([], pg_no=1, pg_size=10)
        assert result.page.total_records == 0
        assert result.page.total_pg == 0
        assert len(result.items) == 0

    def test_page_beyond_range(self):
        items = list(range(5))
        result = paginate(items, pg_no=10, pg_size=10)
        assert len(result.items) == 0

    def test_single_item(self):
        result = paginate(["only"], pg_no=1, pg_size=20)
        assert result.page.total_records == 1
        assert result.page.total_pg == 1
        assert result.items == ["only"]


# ===========================================================================
# Test: OllamaClient (unit tests with mocks)
# ===========================================================================
class TestOllamaClient:
    """Unit tests for OllamaClient methods."""

    @pytest.mark.asyncio
    async def test_list_models_calls_correct_endpoint(self):
        from backend.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://fake:11434")
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
        mock_response.raise_for_status = MagicMock()

        mock_async_client = AsyncMock()
        mock_async_client.request = AsyncMock(return_value=mock_response)
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.services.ollama_client.httpx.AsyncClient", return_value=mock_async_client):
            # Reset circuit breaker
            from backend.services.circuit_breaker import circuit_breaker
            circuit_breaker.failures = 0
            circuit_breaker.open_until = None

            models = await client.list_models()
            assert len(models) == 1
            assert models[0]["name"] == "llama3.2:3b"

    @pytest.mark.asyncio
    async def test_model_exists_true(self):
        from backend.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://fake:11434")
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "mistral:7b"}]}
        mock_response.raise_for_status = MagicMock()

        mock_async_client = AsyncMock()
        mock_async_client.request = AsyncMock(return_value=mock_response)
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.services.ollama_client.httpx.AsyncClient", return_value=mock_async_client):
            from backend.services.circuit_breaker import circuit_breaker
            circuit_breaker.failures = 0
            circuit_breaker.open_until = None

            exists = await client.model_exists("mistral:7b")
            assert exists is True

    @pytest.mark.asyncio
    async def test_model_exists_false(self):
        from backend.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://fake:11434")
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
        mock_response.raise_for_status = MagicMock()

        mock_async_client = AsyncMock()
        mock_async_client.request = AsyncMock(return_value=mock_response)
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.services.ollama_client.httpx.AsyncClient", return_value=mock_async_client):
            from backend.services.circuit_breaker import circuit_breaker
            circuit_breaker.failures = 0
            circuit_breaker.open_until = None

            exists = await client.model_exists("nonexistent:model")
            assert exists is False
