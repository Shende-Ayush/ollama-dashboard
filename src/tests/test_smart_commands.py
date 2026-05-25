"""
Tests for Smart Command Center.

Covers:
- Natural language to command conversion (AI + fallback)
- Command explanation
- Error analysis and severity classification
- Smart autocomplete
- Command usage tracking
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from backend.features.smart_commands.service import SmartCommandService
from backend.features.smart_commands.schemas import (
    CommandSuggestionResponse,
    NaturalLanguageCommandResponse,
    CommandExplanation,
    ErrorAnalysisResponse,
    SmartAutocompleteResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def service():
    """SmartCommandService with mocked Ollama client."""
    mock_client = MagicMock()
    mock_client.list_models = AsyncMock(return_value=[
        {"name": "llama3.2:3b"},
        {"name": "mistral:7b"},
    ])
    mock_client.chat_stream = AsyncMock()
    svc = SmartCommandService(ollama_client=mock_client)
    return svc


# ---------------------------------------------------------------------------
# Test: Fallback command generation (no AI needed)
# ---------------------------------------------------------------------------
class TestFallbackCommandGeneration:
    """Tests for rule-based fallback when AI is unavailable."""

    def test_pull_intent_detects_model(self, service):
        result = service._fallback_command_generation(
            "Download the deepseek reasoning model", "llama3.2:3b"
        )
        assert isinstance(result, NaturalLanguageCommandResponse)
        assert len(result.suggestions) > 0
        assert any("pull" in s.suggested_command for s in result.suggestions)

    def test_list_intent(self, service):
        result = service._fallback_command_generation(
            "Show me all installed models", "llama3.2:3b"
        )
        assert any("ollama list" in s.suggested_command for s in result.suggestions)

    def test_status_intent(self, service):
        result = service._fallback_command_generation(
            "What models are running right now?", "llama3.2:3b"
        )
        assert any("ollama ps" in s.suggested_command for s in result.suggestions)

    def test_remove_intent(self, service):
        result = service._fallback_command_generation(
            "Delete the mistral model", "llama3.2:3b"
        )
        assert any("rm" in s.suggested_command for s in result.suggestions)

    def test_unknown_intent_returns_default(self, service):
        result = service._fallback_command_generation(
            "xyzzy random gibberish", "llama3.2:3b"
        )
        assert len(result.suggestions) > 0
        assert result.suggestions[0].confidence < 0.5



# ---------------------------------------------------------------------------
# Test: Command explanation (fallback)
# ---------------------------------------------------------------------------
class TestCommandExplanation:
    """Tests for rule-based command explanations."""

    def test_explain_ps(self, service):
        result = service._fallback_explain("ollama ps")
        assert isinstance(result, CommandExplanation)
        assert "running" in result.summary.lower()
        assert result.safety_level == "safe"

    def test_explain_pull(self, service):
        result = service._fallback_explain("ollama pull llama3.2:3b")
        assert "download" in result.summary.lower() or "llama" in result.summary.lower()
        assert result.safety_level == "safe"

    def test_explain_rm_is_caution(self, service):
        result = service._fallback_explain("ollama rm mistral:7b")
        assert result.safety_level == "caution"
        assert "remove" in result.summary.lower() or "delete" in result.detailed_explanation.lower()

    def test_explain_list(self, service):
        result = service._fallback_explain("ollama list")
        assert result.safety_level == "safe"
        assert "installed" in result.summary.lower()

    def test_explain_unknown_command(self, service):
        result = service._fallback_explain("ollama unknown_action")
        assert result.safety_level == "caution"


# ---------------------------------------------------------------------------
# Test: Error severity classification
# ---------------------------------------------------------------------------
class TestSeverityClassification:
    """Tests for error severity detection."""

    def test_critical_severity(self, service):
        assert service._classify_severity("fatal: corrupt database") == "critical"
        assert service._classify_severity("data loss detected") == "critical"

    def test_high_severity(self, service):
        assert service._classify_severity("connection refused to host") == "high"
        assert service._classify_severity("out of memory error") == "high"
        assert service._classify_severity("permission denied") == "high"

    def test_medium_severity(self, service):
        assert service._classify_severity("model not found") == "medium"
        assert service._classify_severity("request timeout") == "medium"

    def test_low_severity(self, service):
        assert service._classify_severity("deprecated API warning") == "low"

    def test_default_severity(self, service):
        assert service._classify_severity("something happened") == "medium"


# ---------------------------------------------------------------------------
# Test: Fallback error analysis
# ---------------------------------------------------------------------------
class TestFallbackErrorAnalysis:
    """Tests for rule-based error analysis fallback."""

    def test_connection_refused(self, service):
        result = service._fallback_error_analysis(
            "ollama ps", "connection refused", "high"
        )
        assert isinstance(result, ErrorAnalysisResponse)
        assert "not running" in result.root_cause.lower() or "not accessible" in result.root_cause.lower()
        assert result.severity == "high"

    def test_not_found_error(self, service):
        result = service._fallback_error_analysis(
            "ollama pull xyz", "404 not found", "medium"
        )
        assert "not found" in result.root_cause.lower()

    def test_oom_error(self, service):
        result = service._fallback_error_analysis(
            "ollama run llama3:70b", "out of memory", "high"
        )
        assert "memory" in result.root_cause.lower()

    def test_generic_error(self, service):
        result = service._fallback_error_analysis(
            "ollama pull x", "random error xyz", "medium"
        )
        assert result.severity == "medium"
        assert result.id == "fallback"



# ---------------------------------------------------------------------------
# Test: Smart autocomplete
# ---------------------------------------------------------------------------
class TestSmartAutocomplete:
    """Tests for context-aware autocomplete."""

    @pytest_asyncio.fixture
    async def session(self, db_session):
        return db_session

    @pytest.mark.asyncio
    async def test_autocomplete_command_prefix(self, service, db_session):
        result = await service.get_autocomplete("ollama p", db_session)
        assert isinstance(result, SmartAutocompleteResponse)
        assert len(result.items) > 0
        # Should suggest 'ollama ps' and 'ollama pull'
        completions = [item.completion for item in result.items]
        assert any("ollama ps" in c for c in completions) or any("ollama pull" in c for c in completions)

    @pytest.mark.asyncio
    async def test_autocomplete_model_suggestion(self, service, db_session):
        result = await service.get_autocomplete("ollama pull llama", db_session)
        assert len(result.items) > 0
        # Should suggest llama models
        assert any("llama" in item.completion for item in result.items)

    @pytest.mark.asyncio
    async def test_autocomplete_empty_partial(self, service, db_session):
        result = await service.get_autocomplete("o", db_session)
        # Should return some suggestions
        assert isinstance(result, SmartAutocompleteResponse)

    @pytest.mark.asyncio
    async def test_autocomplete_deduplication(self, service, db_session):
        result = await service.get_autocomplete("ollama", db_session)
        completions = [item.completion for item in result.items]
        assert len(completions) == len(set(completions))  # No duplicates

    @pytest.mark.asyncio
    async def test_autocomplete_max_results(self, service, db_session):
        result = await service.get_autocomplete("ollama pull", db_session)
        assert len(result.items) <= 10


# ---------------------------------------------------------------------------
# Test: Command usage tracking
# ---------------------------------------------------------------------------
class TestCommandTracking:
    """Tests for command usage frequency tracking."""

    @pytest.mark.asyncio
    async def test_track_new_command(self, service, db_session):
        await service.track_command_usage("ollama ps", db_session)
        # Should create a new context entry
        from backend.features.smart_commands.models import CommandContext
        from sqlalchemy import select
        result = await db_session.execute(
            select(CommandContext).where(CommandContext.command_pattern == "ollama ps")
        )
        ctx = result.scalar_one_or_none()
        assert ctx is not None
        assert ctx.frequency == 1

    @pytest.mark.asyncio
    async def test_track_repeated_command_increments(self, service, db_session):
        await service.track_command_usage("ollama list", db_session)
        await service.track_command_usage("ollama list", db_session)

        from backend.features.smart_commands.models import CommandContext
        from sqlalchemy import select
        result = await db_session.execute(
            select(CommandContext).where(CommandContext.command_pattern == "ollama list")
        )
        ctx = result.scalar_one_or_none()
        assert ctx is not None
        assert ctx.frequency == 2


# ---------------------------------------------------------------------------
# Test: JSON parsing utility
# ---------------------------------------------------------------------------
class TestJsonParsing:
    """Tests for robust JSON extraction from LLM output."""

    def test_clean_json(self, service):
        raw = '{"suggestions": [{"command": "ollama ps"}]}'
        result = service._parse_json_response(raw)
        assert "suggestions" in result

    def test_json_with_markdown_fence(self, service):
        raw = '```json\n{"key": "value"}\n```'
        result = service._parse_json_response(raw)
        assert result.get("key") == "value"

    def test_json_embedded_in_text(self, service):
        raw = 'Here is the answer:\n{"answer": 42}\nThat is all.'
        result = service._parse_json_response(raw)
        assert result.get("answer") == 42

    def test_invalid_json_returns_empty(self, service):
        raw = "This is not JSON at all"
        result = service._parse_json_response(raw)
        assert result == {}
