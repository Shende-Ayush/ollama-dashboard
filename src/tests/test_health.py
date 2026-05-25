"""
Tests for Health Monitoring & Auto-Recovery.

Covers:
- Individual component health checks
- System-wide health aggregation
- Incident creation and management
- Auto-recovery mechanisms
- Severity classification
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.features.health.models import HealthIncident
from backend.features.health.schemas import ComponentHealth, SystemHealthResponse
from backend.features.health.service import HealthMonitorService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_client():
    client = MagicMock()
    client.list_models = AsyncMock(return_value=[
        {"name": "llama3.2:3b"},
        {"name": "mistral:7b"},
    ])
    client.list_running = AsyncMock(return_value=[
        {"name": "llama3.2:3b", "size": 2_000_000_000},
    ])
    client.stop_model = AsyncMock(return_value=None)
    return client


@pytest.fixture
def service(mock_client):
    return HealthMonitorService(ollama_client=mock_client)


# ---------------------------------------------------------------------------
# Test: Ollama health check
# ---------------------------------------------------------------------------
class TestOllamaHealthCheck:
    """Tests for Ollama service health monitoring."""

    @pytest.mark.asyncio
    async def test_healthy_ollama(self, service):
        result = await service._check_ollama()
        assert isinstance(result, ComponentHealth)
        assert result.component == "ollama"
        assert result.status == "healthy"
        assert result.details["models_installed"] == 2
        assert result.details["models_running"] == 1

    @pytest.mark.asyncio
    async def test_unhealthy_ollama_on_connection_error(self, service):
        service.client.list_models = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        result = await service._check_ollama()
        assert result.status == "unhealthy"
        assert "Connection refused" in result.details["error"]

    @pytest.mark.asyncio
    async def test_ollama_health_includes_running_models(self, service):
        result = await service._check_ollama()
        assert "running_models" in result.details
        assert "llama3.2:3b" in result.details["running_models"]



# ---------------------------------------------------------------------------
# Test: Database health check
# ---------------------------------------------------------------------------
class TestDatabaseHealthCheck:
    """Tests for database connectivity check."""

    @pytest.mark.asyncio
    async def test_healthy_database(self, service, db_session):
        result = await service._check_database(db_session)
        assert result.component == "postgres"
        assert result.status == "healthy"
        assert result.details["connected"] is True
        assert result.response_time_ms >= 0


# ---------------------------------------------------------------------------
# Test: Disk health check
# ---------------------------------------------------------------------------
class TestDiskHealthCheck:
    """Tests for disk space monitoring."""

    @pytest.mark.asyncio
    async def test_disk_check_returns_usage(self, service):
        result = await service._check_disk()
        assert result.component == "disk"
        assert result.status in ("healthy", "degraded", "unhealthy")
        assert "total_gb" in result.details
        assert "free_gb" in result.details
        assert "usage_percent" in result.details
        assert result.details["total_gb"] > 0


# ---------------------------------------------------------------------------
# Test: GPU health check
# ---------------------------------------------------------------------------
class TestGpuHealthCheck:
    """Tests for GPU monitoring."""

    @pytest.mark.asyncio
    async def test_gpu_check_no_nvidia_smi(self, service):
        """When nvidia-smi is not available, status should be 'unknown'."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await service._check_gpu()
            assert result.component == "gpu"
            assert result.status == "unknown"
            assert result.details.get("gpu_present") is False


# ---------------------------------------------------------------------------
# Test: System health aggregation
# ---------------------------------------------------------------------------
class TestSystemHealth:
    """Tests for full system health check."""

    @pytest.mark.asyncio
    async def test_system_health_returns_all_components(self, service, db_session):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await service.check_system_health(db_session)

        assert isinstance(result, SystemHealthResponse)
        assert result.uptime_seconds >= 0
        components = [c.component for c in result.components]
        assert "ollama" in components
        assert "postgres" in components
        assert "disk" in components

    @pytest.mark.asyncio
    async def test_overall_status_healthy(self, service, db_session):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await service.check_system_health(db_session)

        # All should be healthy (ollama mocked, postgres works, disk ok)
        assert result.overall_status in ("healthy", "degraded")

    @pytest.mark.asyncio
    async def test_overall_status_unhealthy_when_component_fails(
        self, service, db_session
    ):
        service.client.list_models = AsyncMock(
            side_effect=Exception("down")
        )
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await service.check_system_health(db_session)

        assert result.overall_status == "unhealthy"



# ---------------------------------------------------------------------------
# Test: Incident management
# ---------------------------------------------------------------------------
class TestIncidentManagement:
    """Tests for health incident creation and resolution."""

    @pytest.mark.asyncio
    async def test_incident_created_for_unhealthy_component(
        self, service, db_session
    ):
        service.client.list_models = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        # Disable auto-recovery for this test
        service._recovery_handlers = {}

        with patch("subprocess.run", side_effect=FileNotFoundError):
            await service.check_system_health(db_session)

        incidents = await service.list_incidents(db_session)
        assert len(incidents) > 0
        ollama_incidents = [i for i in incidents if i.component == "ollama"]
        assert len(ollama_incidents) == 1
        assert ollama_incidents[0].severity == "critical"
        assert ollama_incidents[0].status == "open"

    @pytest.mark.asyncio
    async def test_no_duplicate_incidents(self, service, db_session):
        service.client.list_models = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        service._recovery_handlers = {}

        with patch("subprocess.run", side_effect=FileNotFoundError):
            await service.check_system_health(db_session)
            await service.check_system_health(db_session)

        incidents = await service.list_incidents(db_session, component="ollama")
        # Should still be only 1 open incident
        assert len(incidents) == 1

    @pytest.mark.asyncio
    async def test_resolve_incident(self, service, db_session):
        # Create an incident manually
        incident = HealthIncident(
            component="ollama",
            severity="critical",
            title="Ollama down",
            description="Connection refused",
            status="open",
        )
        db_session.add(incident)
        await db_session.commit()
        await db_session.refresh(incident)

        await service.resolve_incident(str(incident.id), db_session)

        incidents = await service.list_incidents(db_session, status="resolved")
        assert len(incidents) == 1
        assert incidents[0].resolved_at is not None

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_incident_raises(self, service, db_session):
        with pytest.raises(ValueError, match="not found"):
            await service.resolve_incident(str(uuid.uuid4()), db_session)


# ---------------------------------------------------------------------------
# Test: Auto-recovery
# ---------------------------------------------------------------------------
class TestAutoRecovery:
    """Tests for automatic recovery mechanisms."""

    @pytest.mark.asyncio
    async def test_ollama_recovery_success(self, service):
        """When Ollama becomes reachable after retry, recovery succeeds."""
        success, msg = await service._recover_ollama()
        assert success is True
        assert "recovered" in msg.lower()

    @pytest.mark.asyncio
    async def test_ollama_recovery_failure(self, service):
        """When Ollama stays unreachable, recovery fails."""
        service.client.list_models = AsyncMock(
            side_effect=Exception("still down")
        )
        success, msg = await service._recover_ollama()
        assert success is False
        assert "failed" in msg.lower()

    @pytest.mark.asyncio
    async def test_gpu_recovery_clears_models(self, service):
        """GPU recovery should stop running models."""
        success, msg = await service._recover_gpu()
        assert success is True
        service.client.stop_model.assert_called_once_with("llama3.2:3b")

    @pytest.mark.asyncio
    async def test_gpu_recovery_no_models_running(self, service):
        service.client.list_running = AsyncMock(return_value=[])
        success, msg = await service._recover_gpu()
        assert success is True
        assert "No models" in msg

    @pytest.mark.asyncio
    async def test_trigger_recovery_invalid_component(self, service, db_session):
        with pytest.raises(ValueError, match="No recovery handler"):
            await service.trigger_recovery("invalid_component", "restart", db_session)

    @pytest.mark.asyncio
    async def test_trigger_recovery_stores_action(self, service, db_session):
        result = await service.trigger_recovery("ollama", "restart", db_session)
        assert result.component == "ollama"
        assert result.status == "success"
        assert result.duration_ms >= 0

        # Verify stored in DB
        actions = await service.list_recovery_actions(db_session)
        assert len(actions) == 1
        assert actions[0].component == "ollama"
