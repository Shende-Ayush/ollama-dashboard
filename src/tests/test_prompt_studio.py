"""
Tests for Prompt Engineering Studio.

Covers:
- Template CRUD operations
- Versioning system
- Version restoration
- Token analysis
- Variable resolution
- Comparison summary generation
"""
import uuid

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from backend.features.prompt_studio.models import PromptTemplate, PromptVersion
from backend.features.prompt_studio.schemas import (
    CreatePromptTemplateRequest,
    UpdatePromptTemplateRequest,
    TokenAnalysisResponse,
)
from backend.features.prompt_studio.service import PromptStudioService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def service():
    """PromptStudioService with mocked Ollama client."""
    mock_client = MagicMock()
    mock_client.chat_stream = AsyncMock(return_value=_mock_chat_gen())
    return PromptStudioService(ollama_client=mock_client)


async def _mock_chat_gen():
    yield "Mock response from model."


# ---------------------------------------------------------------------------
# Test: Template CRUD
# ---------------------------------------------------------------------------
class TestTemplateCRUD:
    """Tests for prompt template create, read, update, delete."""

    @pytest.mark.asyncio
    async def test_create_template(self, service, db_session):
        request = CreatePromptTemplateRequest(
            name="Code Review",
            description="Review code for best practices",
            template="Review this code:\n{code}\nFocus: {focus}",
            variables=["code", "focus"],
            tags=["code", "review"],
            model_name="llama3.2:3b",
        )
        result = await service.create_template(request, db_session)

        assert result.name == "Code Review"
        assert result.description == "Review code for best practices"
        assert result.variables == ["code", "focus"]
        assert result.tags == ["code", "review"]
        assert result.version_count == 1
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_get_template(self, service, db_session):
        # Create first
        request = CreatePromptTemplateRequest(
            name="Test Template",
            template="Hello {name}",
            variables=["name"],
        )
        created = await service.create_template(request, db_session)

        # Get by ID
        fetched = await service.get_template(created.id, db_session)
        assert fetched.name == "Test Template"
        assert fetched.template == "Hello {name}"

    @pytest.mark.asyncio
    async def test_get_template_not_found_raises(self, service, db_session):
        with pytest.raises(ValueError, match="not found"):
            await service.get_template(str(uuid.uuid4()), db_session)

    @pytest.mark.asyncio
    async def test_list_templates(self, service, db_session):
        # Create multiple templates
        for i in range(3):
            req = CreatePromptTemplateRequest(
                name=f"Template {i}",
                template=f"Content {i}",
            )
            await service.create_template(req, db_session)

        result = await service.list_templates(db_session)
        assert len(result["items"]) == 3
        assert result["page"]["total_records"] == 3


    @pytest.mark.asyncio
    async def test_list_templates_with_search(self, service, db_session):
        await service.create_template(
            CreatePromptTemplateRequest(name="Python Helper", template="x"),
            db_session,
        )
        await service.create_template(
            CreatePromptTemplateRequest(name="JS Helper", template="y"),
            db_session,
        )

        result = await service.list_templates(db_session, search="Python")
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Python Helper"

    @pytest.mark.asyncio
    async def test_update_template_metadata(self, service, db_session):
        created = await service.create_template(
            CreatePromptTemplateRequest(name="Original", template="content"),
            db_session,
        )

        updated = await service.update_template(
            created.id,
            UpdatePromptTemplateRequest(name="Updated Name", tags=["new-tag"]),
            db_session,
        )
        assert updated.name == "Updated Name"
        assert updated.tags == ["new-tag"]

    @pytest.mark.asyncio
    async def test_update_template_content_creates_version(self, service, db_session):
        created = await service.create_template(
            CreatePromptTemplateRequest(name="Versioned", template="v1 content"),
            db_session,
        )

        await service.update_template(
            created.id,
            UpdatePromptTemplateRequest(
                template="v2 content",
                change_notes="Updated template body",
            ),
            db_session,
        )

        versions = await service.get_versions(created.id, db_session)
        assert len(versions) == 2
        assert versions[0].version_number == 2
        assert versions[0].template_content == "v2 content"
        assert versions[0].change_notes == "Updated template body"

    @pytest.mark.asyncio
    async def test_delete_template(self, service, db_session):
        created = await service.create_template(
            CreatePromptTemplateRequest(name="ToDelete", template="x"),
            db_session,
        )

        await service.delete_template(created.id, db_session)

        with pytest.raises(ValueError, match="not found"):
            await service.get_template(created.id, db_session)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, service, db_session):
        with pytest.raises(ValueError, match="not found"):
            await service.delete_template(str(uuid.uuid4()), db_session)


# ---------------------------------------------------------------------------
# Test: Versioning
# ---------------------------------------------------------------------------
class TestVersioning:
    """Tests for prompt version management."""

    @pytest.mark.asyncio
    async def test_initial_version_created(self, service, db_session):
        created = await service.create_template(
            CreatePromptTemplateRequest(
                name="V Test", template="Initial", variables=["a"]
            ),
            db_session,
        )

        versions = await service.get_versions(created.id, db_session)
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].template_content == "Initial"
        assert versions[0].change_notes == "Initial version"

    @pytest.mark.asyncio
    async def test_restore_version(self, service, db_session):
        created = await service.create_template(
            CreatePromptTemplateRequest(name="Restore", template="v1"),
            db_session,
        )

        # Update to v2
        await service.update_template(
            created.id,
            UpdatePromptTemplateRequest(template="v2"),
            db_session,
        )

        # Restore to v1
        restored = await service.restore_version(created.id, 1, db_session)
        assert restored.template == "v1"

        # Should have 3 versions now (v1, v2, restored)
        versions = await service.get_versions(created.id, db_session)
        assert len(versions) == 3
        assert versions[0].change_notes == "Restored from version 1"

    @pytest.mark.asyncio
    async def test_restore_nonexistent_version_raises(self, service, db_session):
        created = await service.create_template(
            CreatePromptTemplateRequest(name="X", template="y"),
            db_session,
        )

        with pytest.raises(ValueError, match="not found"):
            await service.restore_version(created.id, 99, db_session)



# ---------------------------------------------------------------------------
# Test: Token analysis
# ---------------------------------------------------------------------------
class TestTokenAnalysis:
    """Tests for prompt token analysis."""

    def test_basic_token_count(self, service):
        result = service.analyze_tokens("Hello world, this is a test.")
        assert isinstance(result, TokenAnalysisResponse)
        assert result.text_length == len("Hello world, this is a test.")
        assert result.estimated_tokens > 0
        assert "4K context" in result.estimated_cost_context

    def test_code_detection(self, service):
        code = "def hello():\n    return 'world'\nimport os\n"
        result = service.analyze_tokens(code)
        assert result.breakdown["code_lines"] >= 2

    def test_long_text_context_usage(self, service):
        # 1000 tokens approx = 4000 chars
        text = "word " * 1000
        result = service.analyze_tokens(text)
        assert result.estimated_tokens > 100
        assert "context_usage" in result.breakdown

    def test_empty_line_handling(self, service):
        text = "line1\n\n\nline4"
        result = service.analyze_tokens(text)
        assert result.breakdown["total_lines"] == 4


# ---------------------------------------------------------------------------
# Test: Variable resolution
# ---------------------------------------------------------------------------
class TestVariableResolution:
    """Tests for template variable substitution."""

    def test_single_variable(self, service):
        result = service._resolve_variables("Hello {name}!", {"name": "World"})
        assert result == "Hello World!"

    def test_multiple_variables(self, service):
        template = "{greeting} {name}, welcome to {place}."
        variables = {"greeting": "Hi", "name": "Alice", "place": "Wonderland"}
        result = service._resolve_variables(template, variables)
        assert result == "Hi Alice, welcome to Wonderland."

    def test_missing_variable_left_unchanged(self, service):
        result = service._resolve_variables("Hello {name}!", {})
        assert result == "Hello {name}!"

    def test_empty_variables(self, service):
        result = service._resolve_variables("No vars here.", {})
        assert result == "No vars here."


# ---------------------------------------------------------------------------
# Test: Comparison summary
# ---------------------------------------------------------------------------
class TestComparisonSummary:
    """Tests for multi-model comparison summary generation."""

    def test_summary_with_results(self, service):
        from backend.features.prompt_studio.schemas import PromptTestResultResponse

        results = [
            PromptTestResultResponse(
                model_name="llama3.2:3b",
                response="Answer A",
                tokens_input=10,
                tokens_output=50,
                latency_ms=200,
                quality_score=None,
            ),
            PromptTestResultResponse(
                model_name="mistral:7b",
                response="Answer B longer",
                tokens_input=10,
                tokens_output=80,
                latency_ms=500,
                quality_score=None,
            ),
        ]
        summary = service._generate_comparison_summary(results)
        assert "Tested 2" in summary
        assert "Fastest: llama3.2:3b" in summary
        assert "Most detailed: mistral:7b" in summary

    def test_summary_empty_results(self, service):
        summary = service._generate_comparison_summary([])
        assert "No results" in summary

    def test_summary_all_failed(self, service):
        from backend.features.prompt_studio.schemas import PromptTestResultResponse

        results = [
            PromptTestResultResponse(
                model_name="model1",
                response="Error",
                tokens_input=10,
                tokens_output=0,
                latency_ms=100,
                quality_score=None,
            ),
        ]
        summary = service._generate_comparison_summary(results)
        assert "failed" in summary.lower()
