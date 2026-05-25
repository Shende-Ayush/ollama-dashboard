"""
Tests for Agents Framework.

Covers:
- Agent CRUD operations
- Agent type validation
- Execution engine
- Task completion detection
- Response parsing
- Orchestration strategies
- Auto-selection
"""
import uuid

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.features.agents.models import AgentConfig, AgentExecution
from backend.features.agents.schemas import (
    AGENT_TYPES,
    CreateAgentRequest,
    UpdateAgentRequest,
    AgentConfigResponse,
)
from backend.features.agents.service import (
    AgentEngine,
    AgentOrchestratorService,
    DEFAULT_SYSTEM_PROMPTS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_client():
    client = MagicMock()
    client.list_models = AsyncMock(return_value=[{"name": "llama3.2:3b"}])
    client.chat_stream = MagicMock(return_value=_mock_agent_stream())
    return client


@pytest.fixture
def service(mock_client):
    return AgentOrchestratorService(ollama_client=mock_client)


@pytest.fixture
def engine(mock_client):
    return AgentEngine(ollama_client=mock_client)


async def _mock_agent_stream():
    yield "I analyzed the task.\n"
    yield "Action: implement_api\n"
    yield "Reasoning: The task requires creating a new endpoint.\n"
    yield "TASK_COMPLETE"


# ---------------------------------------------------------------------------
# Test: Agent CRUD
# ---------------------------------------------------------------------------
class TestAgentCRUD:
    """Tests for agent configuration management."""

    @pytest.mark.asyncio
    async def test_create_agent(self, service, db_session):
        request = CreateAgentRequest(
            name="Backend Engineer",
            agent_type="backend_engineer",
            description="Implements APIs",
            system_prompt="You are a backend engineer...",
            capabilities=["code_generation", "api_design"],
            model_name="llama3.2:3b",
            max_iterations=5,
            temperature=0.7,
        )
        result = await service.create_agent(request, db_session)

        assert isinstance(result, AgentConfigResponse)
        assert result.name == "Backend Engineer"
        assert result.agent_type == "backend_engineer"
        assert result.capabilities == ["code_generation", "api_design"]
        assert result.max_iterations == 5
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_create_agent_invalid_type_raises(self, service, db_session):
        request = CreateAgentRequest(
            name="Invalid",
            agent_type="nonexistent_type",
            system_prompt="x" * 10,
            model_name="llama3.2:3b",
        )
        with pytest.raises(ValueError, match="Invalid agent type"):
            await service.create_agent(request, db_session)

    @pytest.mark.asyncio
    async def test_get_agent(self, service, db_session):
        request = CreateAgentRequest(
            name="Test Agent",
            agent_type="debugger",
            system_prompt="You debug things.",
            model_name="llama3.2:3b",
        )
        created = await service.create_agent(request, db_session)
        fetched = await service.get_agent(created.id, db_session)
        assert fetched.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_get_nonexistent_agent_raises(self, service, db_session):
        with pytest.raises(ValueError, match="not found"):
            await service.get_agent(str(uuid.uuid4()), db_session)


    @pytest.mark.asyncio
    async def test_list_agents(self, service, db_session):
        for i, atype in enumerate(["debugger", "testing", "devops"]):
            await service.create_agent(
                CreateAgentRequest(
                    name=f"Agent {i}",
                    agent_type=atype,
                    system_prompt="prompt" * 3,
                    model_name="llama3.2:3b",
                ),
                db_session,
            )

        result = await service.list_agents(db_session)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_agents_filter_by_type(self, service, db_session):
        await service.create_agent(
            CreateAgentRequest(
                name="Debug1",
                agent_type="debugger",
                system_prompt="prompt" * 3,
                model_name="llama3.2:3b",
            ),
            db_session,
        )
        await service.create_agent(
            CreateAgentRequest(
                name="Test1",
                agent_type="testing",
                system_prompt="prompt" * 3,
                model_name="llama3.2:3b",
            ),
            db_session,
        )

        result = await service.list_agents(db_session, agent_type="debugger")
        assert len(result) == 1
        assert result[0].agent_type == "debugger"

    @pytest.mark.asyncio
    async def test_update_agent(self, service, db_session):
        created = await service.create_agent(
            CreateAgentRequest(
                name="Original",
                agent_type="devops",
                system_prompt="prompt" * 3,
                model_name="llama3.2:3b",
            ),
            db_session,
        )

        updated = await service.update_agent(
            created.id,
            UpdateAgentRequest(name="Renamed", max_iterations=20),
            db_session,
        )
        assert updated.name == "Renamed"
        assert updated.max_iterations == 20

    @pytest.mark.asyncio
    async def test_deactivate_agent(self, service, db_session):
        created = await service.create_agent(
            CreateAgentRequest(
                name="Active Agent",
                agent_type="testing",
                system_prompt="prompt" * 3,
                model_name="llama3.2:3b",
            ),
            db_session,
        )

        updated = await service.update_agent(
            created.id,
            UpdateAgentRequest(is_active=False),
            db_session,
        )
        assert updated.is_active is False

        # Should not appear in active-only listing
        active_agents = await service.list_agents(db_session, active_only=True)
        assert all(a.id != created.id for a in active_agents)

    @pytest.mark.asyncio
    async def test_delete_agent(self, service, db_session):
        created = await service.create_agent(
            CreateAgentRequest(
                name="ToDelete",
                agent_type="performance",
                system_prompt="prompt" * 3,
                model_name="llama3.2:3b",
            ),
            db_session,
        )
        await service.delete_agent(created.id, db_session)

        with pytest.raises(ValueError, match="not found"):
            await service.get_agent(created.id, db_session)



# ---------------------------------------------------------------------------
# Test: Agent Engine internals
# ---------------------------------------------------------------------------
class TestAgentEngine:
    """Tests for agent execution engine utilities."""

    def test_task_complete_detection(self, engine):
        assert engine._is_task_complete("Done. TASK_COMPLETE") is True
        assert engine._is_task_complete("I have finished the task.") is True
        assert engine._is_task_complete("Still working on it...") is False

    def test_response_parsing_with_action(self, engine):
        response = "Action: implement_api\nReasoning: Need to build the endpoint."
        action, reasoning = engine._parse_agent_response(response)
        assert action == "implement_api"
        assert "endpoint" in reasoning

    def test_response_parsing_no_action(self, engine):
        response = "This is just a plain response without structure."
        action, reasoning = engine._parse_agent_response(response)
        assert action == "reasoning"
        assert len(reasoning) > 0

    def test_build_task_prompt_no_context(self, engine):
        prompt = engine._build_task_prompt("Fix the bug", {})
        assert "## Task" in prompt
        assert "Fix the bug" in prompt
        assert "## Instructions" in prompt
        assert "TASK_COMPLETE" in prompt

    def test_build_task_prompt_with_context(self, engine):
        ctx = {"file": "main.py", "error": "ImportError"}
        prompt = engine._build_task_prompt("Debug this", ctx)
        assert "## Context" in prompt
        assert "main.py" in prompt
        assert "ImportError" in prompt


# ---------------------------------------------------------------------------
# Test: Agent types and defaults
# ---------------------------------------------------------------------------
class TestAgentTypes:
    """Tests for agent type validation and default prompts."""

    def test_all_types_have_default_prompts(self):
        for agent_type in AGENT_TYPES:
            assert agent_type in DEFAULT_SYSTEM_PROMPTS

    def test_agent_types_list_not_empty(self):
        assert len(AGENT_TYPES) >= 7

    def test_default_prompts_are_meaningful(self):
        for prompt in DEFAULT_SYSTEM_PROMPTS.values():
            assert len(prompt) > 50


# ---------------------------------------------------------------------------
# Test: Auto-selection
# ---------------------------------------------------------------------------
class TestAutoSelection:
    """Tests for automatic agent selection based on task keywords."""

    @pytest.mark.asyncio
    async def test_selects_backend_for_api_task(self, service, db_session):
        # Create a backend agent
        await service.create_agent(
            CreateAgentRequest(
                name="BE Agent",
                agent_type="backend_engineer",
                system_prompt="prompt" * 3,
                model_name="llama3.2:3b",
            ),
            db_session,
        )

        agents = await service._auto_select_agents(
            "Create a REST API endpoint for user registration", db_session
        )
        assert len(agents) > 0
        assert any(a.agent_type == "backend_engineer" for a in agents)

    @pytest.mark.asyncio
    async def test_selects_debugger_for_bug_task(self, service, db_session):
        await service.create_agent(
            CreateAgentRequest(
                name="Bug Agent",
                agent_type="debugger",
                system_prompt="prompt" * 3,
                model_name="llama3.2:3b",
            ),
            db_session,
        )

        agents = await service._auto_select_agents(
            "Fix the bug causing errors in production", db_session
        )
        assert any(a.agent_type == "debugger" for a in agents)

    @pytest.mark.asyncio
    async def test_selects_security_for_vulnerability(self, service, db_session):
        await service.create_agent(
            CreateAgentRequest(
                name="Sec Agent",
                agent_type="security_auditor",
                system_prompt="prompt" * 3,
                model_name="llama3.2:3b",
            ),
            db_session,
        )

        agents = await service._auto_select_agents(
            "Check for security vulnerabilities in auth module", db_session
        )
        assert any(a.agent_type == "security_auditor" for a in agents)
