"""
Tests for API endpoints (integration-level).

Uses the FastAPI test client to verify endpoint behavior.
Covers: health, prompt studio, smart commands, and agents API routes.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# Test: Health API endpoints
# ===========================================================================
class TestHealthAPI:
    """Tests for /api/health/* endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_healthz_endpoint(self, client):
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_system_health_endpoint(self, client):
        with patch(
            "backend.features.health.service.HealthMonitorService._check_ollama",
            new=AsyncMock(return_value=_mock_healthy_component("ollama")),
        ), patch(
            "backend.features.health.service.HealthMonitorService._check_gpu",
            new=AsyncMock(return_value=_mock_healthy_component("gpu")),
        ), patch(
            "backend.features.health.service.HealthMonitorService._check_disk",
            new=AsyncMock(return_value=_mock_healthy_component("disk")),
        ):
            response = await client.get("/api/health/system")
            assert response.status_code == 200
            data = response.json()
            assert "overall_status" in data
            assert "components" in data
            assert "uptime_seconds" in data

    @pytest.mark.asyncio
    async def test_incidents_endpoint_empty(self, client):
        response = await client.get("/api/health/incidents")
        assert response.status_code == 200
        assert response.json()["items"] == []

    @pytest.mark.asyncio
    async def test_recovery_actions_endpoint_empty(self, client):
        response = await client.get("/api/health/recovery-actions")
        assert response.status_code == 200
        assert response.json()["items"] == []

    @pytest.mark.asyncio
    async def test_trigger_recovery_invalid_component(self, client):
        response = await client.post(
            "/api/health/recover",
            json={"component": "nonexistent", "action_type": "restart"},
        )
        assert response.status_code == 400



# ===========================================================================
# Test: Prompt Studio API endpoints
# ===========================================================================
class TestPromptStudioAPI:
    """Tests for /api/prompt-studio/* endpoints."""

    @pytest.mark.asyncio
    async def test_create_template(self, client):
        response = await client.post(
            "/api/prompt-studio/templates",
            json={
                "name": "Test Template",
                "description": "A test",
                "template": "Hello {name}, welcome to {place}.",
                "variables": ["name", "place"],
                "tags": ["greeting"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Template"
        assert data["variables"] == ["name", "place"]
        assert data["version_count"] == 1

    @pytest.mark.asyncio
    async def test_list_templates_empty(self, client):
        response = await client.get("/api/prompt-studio/templates")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "page" in data

    @pytest.mark.asyncio
    async def test_create_and_get_template(self, client):
        # Create
        create_resp = await client.post(
            "/api/prompt-studio/templates",
            json={"name": "Fetch Me", "template": "content here"},
        )
        template_id = create_resp.json()["id"]

        # Get
        get_resp = await client.get(f"/api/prompt-studio/templates/{template_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Fetch Me"

    @pytest.mark.asyncio
    async def test_get_nonexistent_template_404(self, client):
        import uuid
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/prompt-studio/templates/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_template(self, client):
        create_resp = await client.post(
            "/api/prompt-studio/templates",
            json={"name": "Original", "template": "v1"},
        )
        template_id = create_resp.json()["id"]

        update_resp = await client.put(
            f"/api/prompt-studio/templates/{template_id}",
            json={"name": "Updated"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_delete_template(self, client):
        create_resp = await client.post(
            "/api/prompt-studio/templates",
            json={"name": "Delete Me", "template": "x"},
        )
        template_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/prompt-studio/templates/{template_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_token_analysis(self, client):
        response = await client.post(
            "/api/prompt-studio/analyze-tokens",
            json={"text": "This is a test prompt for analysis."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["text_length"] > 0
        assert data["estimated_tokens"] > 0
        assert "breakdown" in data

    @pytest.mark.asyncio
    async def test_get_versions(self, client):
        create_resp = await client.post(
            "/api/prompt-studio/templates",
            json={"name": "Versioned", "template": "v1"},
        )
        template_id = create_resp.json()["id"]

        versions_resp = await client.get(
            f"/api/prompt-studio/templates/{template_id}/versions"
        )
        assert versions_resp.status_code == 200
        assert len(versions_resp.json()["items"]) == 1



# ===========================================================================
# Test: Smart Commands API endpoints
# ===========================================================================
class TestSmartCommandsAPI:
    """Tests for /api/smart-commands/* endpoints."""

    @pytest.mark.asyncio
    async def test_explain_command(self, client):
        with patch(
            "backend.features.smart_commands.service.SmartCommandService.explain_command",
            new=AsyncMock(return_value=MagicMock(
                model_dump=lambda: {
                    "command": "ollama ps",
                    "summary": "List running models",
                    "detailed_explanation": "Shows models in memory",
                    "parameters": [],
                    "side_effects": [],
                    "safety_level": "safe",
                }
            )),
        ):
            response = await client.post(
                "/api/smart-commands/explain",
                json={"command": "ollama ps"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["command"] == "ollama ps"
            assert data["safety_level"] == "safe"

    @pytest.mark.asyncio
    async def test_autocomplete(self, client):
        response = await client.get("/api/smart-commands/autocomplete?q=ollama")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    @pytest.mark.asyncio
    async def test_autocomplete_min_length(self, client):
        response = await client.get("/api/smart-commands/autocomplete?q=")
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_track_usage(self, client):
        response = await client.post(
            "/api/smart-commands/track-usage?command=ollama+ps"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "tracked"


# ===========================================================================
# Test: Agents API endpoints
# ===========================================================================
class TestAgentsAPI:
    """Tests for /api/agents/* endpoints."""

    @pytest.mark.asyncio
    async def test_list_agent_types(self, client):
        response = await client.get("/api/agents/types")
        assert response.status_code == 200
        data = response.json()
        assert "types" in data
        assert "backend_engineer" in data["types"]
        assert "debugger" in data["types"]

    @pytest.mark.asyncio
    async def test_create_agent(self, client):
        response = await client.post(
            "/api/agents",
            json={
                "name": "Test Backend Agent",
                "agent_type": "backend_engineer",
                "description": "A test agent",
                "system_prompt": "You are a helpful backend engineer with expertise in Python and FastAPI.",
                "capabilities": ["api_design"],
                "model_name": "llama3.2:3b",
                "max_iterations": 5,
                "temperature": 0.7,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Backend Agent"
        assert data["agent_type"] == "backend_engineer"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_agent_invalid_type(self, client):
        response = await client.post(
            "/api/agents",
            json={
                "name": "Bad Agent",
                "agent_type": "invalid_type",
                "system_prompt": "x" * 10,
                "model_name": "llama3.2:3b",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, client):
        response = await client.get("/api/agents")
        assert response.status_code == 200
        assert "items" in response.json()

    @pytest.mark.asyncio
    async def test_get_nonexistent_agent_404(self, client):
        import uuid
        response = await client.get(f"/api/agents/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_and_delete_agent(self, client):
        # Create
        create_resp = await client.post(
            "/api/agents",
            json={
                "name": "Deletable",
                "agent_type": "testing",
                "system_prompt": "You are a testing expert specializing in Python.",
                "model_name": "llama3.2:3b",
            },
        )
        agent_id = create_resp.json()["id"]

        # Delete
        del_resp = await client.delete(f"/api/agents/{agent_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Verify gone
        get_resp = await client.get(f"/api/agents/{agent_id}")
        assert get_resp.status_code == 404



# ===========================================================================
# Helpers
# ===========================================================================
def _mock_healthy_component(name: str):
    """Create a mock healthy ComponentHealth."""
    from backend.features.health.schemas import ComponentHealth
    from datetime import datetime, timezone

    return ComponentHealth(
        component=name,
        status="healthy",
        response_time_ms=50,
        details={"mock": True},
        last_checked=datetime.now(timezone.utc),
    )
