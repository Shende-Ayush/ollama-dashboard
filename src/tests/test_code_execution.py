"""
Tests for code execution sandbox feature.

Covers:
- Runtime listing
- Code validation (safe code passes, dangerous code blocked)
- Python execution (simple print, math)
- JavaScript execution (console.log)
- Timeout enforcement
- Security guard blocking dangerous code
- API endpoint tests
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.features.code_execution.executor import CodeExecutor
from backend.features.code_execution.guard import ExecutionGuard
from backend.features.code_execution.limiter import ResourceLimiter, ResourceLimits
from backend.features.code_execution.runtimes import (
    get_runtime,
    is_supported,
    list_runtimes,
)
from backend.features.code_execution.schemas import ExecuteRequest
from backend.features.code_execution.service import ExecutionService


# ---------------------------------------------------------------------------
# Runtime tests
# ---------------------------------------------------------------------------
class TestRuntimes:
    """Tests for runtime registry."""

    def test_list_runtimes_returns_all(self):
        runtimes = list_runtimes()
        assert len(runtimes) == 5
        languages = {r.language for r in runtimes}
        assert "python" in languages
        assert "javascript" in languages
        assert "typescript" in languages
        assert "bash" in languages
        assert "go" in languages

    def test_get_runtime_python(self):
        rt = get_runtime("python")
        assert rt is not None
        assert rt["image"] == "python:3.12-slim"
        assert rt["cmd"] == ["python", "-c"]

    def test_get_runtime_case_insensitive(self):
        rt = get_runtime("Python")
        assert rt is not None

    def test_get_runtime_unknown(self):
        rt = get_runtime("cobol")
        assert rt is None

    def test_is_supported(self):
        assert is_supported("python") is True
        assert is_supported("javascript") is True
        assert is_supported("rust") is False


# ---------------------------------------------------------------------------
# Security guard tests
# ---------------------------------------------------------------------------
class TestExecutionGuard:
    """Tests for security guard."""

    def setup_method(self):
        self.guard = ExecutionGuard()

    def test_safe_python_code(self):
        code = 'print("Hello, world!")'
        is_safe, violations = self.guard.is_execution_allowed(code, "python")
        assert is_safe is True
        assert violations == []

    def test_dangerous_python_os_system(self):
        code = 'import os; os.system("rm -rf /")'
        is_safe, violations = self.guard.is_execution_allowed(code, "python")
        assert is_safe is False
        assert len(violations) > 0

    def test_dangerous_python_subprocess(self):
        code = "import subprocess; subprocess.run(['ls'])"
        is_safe, violations = self.guard.is_execution_allowed(code, "python")
        assert is_safe is False
        assert any("subprocess" in v for v in violations)

    def test_dangerous_python_eval(self):
        code = 'eval("__import__(\'os\').system(\'ls\')")'
        is_safe, violations = self.guard.is_execution_allowed(code, "python")
        assert is_safe is False

    def test_safe_javascript_code(self):
        code = 'console.log("Hello, world!")'
        is_safe, violations = self.guard.is_execution_allowed(code, "javascript")
        assert is_safe is True
        assert violations == []

    def test_dangerous_javascript_child_process(self):
        code = "const { exec } = require('child_process')"
        is_safe, violations = self.guard.is_execution_allowed(code, "javascript")
        assert is_safe is False

    def test_dangerous_bash_rm_rf(self):
        code = "rm -rf /"
        is_safe, violations = self.guard.is_execution_allowed(code, "bash")
        assert is_safe is False

    def test_safe_bash_code(self):
        code = 'echo "Hello, world!"'
        is_safe, violations = self.guard.is_execution_allowed(code, "bash")
        assert is_safe is True

    def test_validate_returns_scan_result(self):
        code = 'print("safe")'
        result = self.guard.validate(code, "python")
        assert result.is_safe is True
        assert result.risk_level == "low"

    def test_validation_result_conversion(self):
        code = "import subprocess"
        result = self.guard.validate(code, "python")
        validation = self.guard.to_validation_result(result)
        assert validation.is_safe is False
        assert len(validation.violations) > 0
        assert validation.risk_level in ("medium", "high", "critical")


# ---------------------------------------------------------------------------
# Resource limiter tests
# ---------------------------------------------------------------------------
class TestResourceLimiter:
    """Tests for resource limiter."""

    def setup_method(self):
        self.limiter = ResourceLimiter()

    def test_calculate_limits_default(self):
        limits = self.limiter.calculate_limits(30, 128, "python")
        assert limits.timeout_seconds == 30
        assert limits.memory_mb == 128
        assert limits.network_enabled is False

    def test_calculate_limits_clamped_to_max(self):
        limits = self.limiter.calculate_limits(999, 9999, "python")
        assert limits.timeout_seconds <= ResourceLimiter.MAX_TIMEOUT
        assert limits.memory_mb <= ResourceLimiter.MAX_MEMORY_MB

    def test_calculate_limits_go_gets_more_cpu(self):
        limits = self.limiter.calculate_limits(60, 256, "go")
        assert limits.cpu_count == 1.0

    def test_to_docker_config(self):
        limits = ResourceLimits(
            timeout_seconds=30, memory_mb=128, cpu_count=0.5
        )
        config = self.limiter.to_docker_config(limits)
        assert config["mem_limit"] == "128m"
        assert config["network_disabled"] is True
        assert config["read_only"] is True

    def test_minimum_memory(self):
        limits = self.limiter.calculate_limits(30, 1, "python")
        assert limits.memory_mb >= 32


# ---------------------------------------------------------------------------
# Executor tests (integration - requires python/node available)
# ---------------------------------------------------------------------------
class TestCodeExecutor:
    """Tests for code executor (subprocess-based)."""

    def setup_method(self):
        self.executor = CodeExecutor()

    @pytest.mark.asyncio
    async def test_python_hello_world(self):
        limits = ResourceLimits(timeout_seconds=10)
        result = await self.executor.run(
            code='print("Hello, world!")',
            language="python",
            limits=limits,
        )
        assert result.exit_code == 0
        assert result.stdout == "Hello, world!"
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_python_math(self):
        limits = ResourceLimits(timeout_seconds=10)
        result = await self.executor.run(
            code="print(2 + 2)",
            language="python",
            limits=limits,
        )
        assert result.exit_code == 0
        assert result.stdout == "4"

    @pytest.mark.asyncio
    async def test_python_with_stdin(self):
        limits = ResourceLimits(timeout_seconds=10)
        result = await self.executor.run(
            code="import sys; print(sys.stdin.read().strip().upper())",
            language="python",
            limits=limits,
            stdin="hello",
        )
        assert result.exit_code == 0
        assert result.stdout == "HELLO"

    @pytest.mark.asyncio
    async def test_python_stderr(self):
        limits = ResourceLimits(timeout_seconds=10)
        result = await self.executor.run(
            code='import sys; print("error", file=sys.stderr)',
            language="python",
            limits=limits,
        )
        assert result.exit_code == 0
        assert "error" in result.stderr

    @pytest.mark.asyncio
    async def test_python_syntax_error(self):
        limits = ResourceLimits(timeout_seconds=10)
        result = await self.executor.run(
            code="def foo(:",
            language="python",
            limits=limits,
        )
        assert result.exit_code != 0
        assert "SyntaxError" in result.stderr

    @pytest.mark.asyncio
    async def test_javascript_hello_world(self):
        limits = ResourceLimits(timeout_seconds=10)
        result = await self.executor.run(
            code='console.log("Hello from JS")',
            language="javascript",
            limits=limits,
        )
        assert result.exit_code == 0
        assert result.stdout == "Hello from JS"

    @pytest.mark.asyncio
    async def test_javascript_math(self):
        limits = ResourceLimits(timeout_seconds=10)
        result = await self.executor.run(
            code="console.log(3 * 7)",
            language="javascript",
            limits=limits,
        )
        assert result.exit_code == 0
        assert result.stdout == "21"

    @pytest.mark.asyncio
    async def test_timeout_enforcement(self):
        limits = ResourceLimits(timeout_seconds=2)
        result = await self.executor.run(
            code="import time; time.sleep(10)",
            language="python",
            limits=limits,
        )
        assert result.timed_out is True
        assert result.exit_code == -1
        assert result.duration_ms >= 2000

    @pytest.mark.asyncio
    async def test_unsupported_language(self):
        limits = ResourceLimits(timeout_seconds=10)
        result = await self.executor.run(
            code="puts 'hello'",
            language="ruby",
            limits=limits,
        )
        assert result.exit_code == 1
        assert "Unsupported language" in result.stderr

    @pytest.mark.asyncio
    async def test_bash_execution(self):
        limits = ResourceLimits(timeout_seconds=10)
        result = await self.executor.run(
            code='echo "Hello from bash"',
            language="bash",
            limits=limits,
        )
        assert result.exit_code == 0
        assert result.stdout == "Hello from bash"


# ---------------------------------------------------------------------------
# Service tests (integration with DB)
# ---------------------------------------------------------------------------
class TestExecutionService:
    """Tests for the execution service orchestrator."""

    def setup_method(self):
        self.service = ExecutionService()

    @pytest.mark.asyncio
    async def test_execute_python(self, db_session):
        request = ExecuteRequest(
            code='print("service test")',
            language="python",
            timeout=10,
        )
        response = await self.service.execute(request, db_session)
        assert response.status == "completed"
        assert response.stdout == "service test"
        assert response.exit_code == 0
        assert response.id is not None

    @pytest.mark.asyncio
    async def test_execute_unsupported_language(self, db_session):
        request = ExecuteRequest(
            code="puts 'hello'",
            language="ruby",
            timeout=10,
        )
        with pytest.raises(ValueError, match="Unsupported language"):
            await self.service.execute(request, db_session)

    @pytest.mark.asyncio
    async def test_execute_dangerous_code_rejected(self, db_session):
        request = ExecuteRequest(
            code='import os; os.system("rm -rf /")',
            language="python",
            timeout=10,
        )
        with pytest.raises(ValueError, match="security validation"):
            await self.service.execute(request, db_session)

    @pytest.mark.asyncio
    async def test_get_execution(self, db_session):
        request = ExecuteRequest(
            code="print(42)",
            language="python",
            timeout=10,
        )
        response = await self.service.execute(request, db_session)
        fetched = await self.service.get_execution(str(response.id), db_session)
        assert fetched.id == response.id
        assert fetched.stdout == "42"

    @pytest.mark.asyncio
    async def test_get_execution_not_found(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            await self.service.get_execution(
                "00000000-0000-0000-0000-000000000000", db_session
            )

    @pytest.mark.asyncio
    async def test_validate_safe_code(self):
        result = await self.service.validate_code('print("hi")', "python")
        assert result.is_safe is True
        assert result.violations == []
        assert result.risk_level == "low"

    @pytest.mark.asyncio
    async def test_validate_dangerous_code(self):
        result = await self.service.validate_code(
            "import subprocess", "python"
        )
        assert result.is_safe is False
        assert len(result.violations) > 0

    @pytest.mark.asyncio
    async def test_list_runtimes_from_service(self):
        runtimes = await self.service.list_runtimes()
        assert len(runtimes) == 5
        assert all(r.is_active for r in runtimes)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------
class TestCodeExecutionAPI:
    """Tests for code execution REST API endpoints."""

    @pytest.mark.asyncio
    async def test_list_runtimes(self, client):
        resp = await client.get("/api/execute/runtimes")
        assert resp.status_code == 200
        data = resp.json()
        assert "runtimes" in data
        assert len(data["runtimes"]) == 5

    @pytest.mark.asyncio
    async def test_execute_python_code(self, client):
        resp = await client.post(
            "/api/execute",
            json={
                "code": 'print("api test")',
                "language": "python",
                "timeout": 10,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["stdout"] == "api test"
        assert data["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_execute_dangerous_code_rejected(self, client):
        resp = await client.post(
            "/api/execute",
            json={
                "code": "import subprocess; subprocess.run(['ls'])",
                "language": "python",
                "timeout": 10,
            },
        )
        assert resp.status_code == 400
        assert "security validation" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_execute_unsupported_language(self, client):
        resp = await client.post(
            "/api/execute",
            json={
                "code": "puts 'hello'",
                "language": "ruby",
                "timeout": 10,
            },
        )
        assert resp.status_code == 400
        assert "Unsupported language" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_validate_endpoint(self, client):
        resp = await client.post(
            "/api/execute/validate",
            json={
                "code": 'print("safe")',
                "language": "python",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_safe"] is True
        assert data["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_validate_endpoint_dangerous(self, client):
        resp = await client.post(
            "/api/execute/validate",
            json={
                "code": 'import os; os.system("ls")',
                "language": "python",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_safe"] is False
        assert len(data["violations"]) > 0

    @pytest.mark.asyncio
    async def test_get_execution_by_id(self, client):
        # First execute something
        resp = await client.post(
            "/api/execute",
            json={
                "code": "print(123)",
                "language": "python",
                "timeout": 10,
            },
        )
        assert resp.status_code == 200
        exec_id = resp.json()["id"]

        # Then fetch it
        resp = await client.get(f"/api/execute/{exec_id}")
        assert resp.status_code == 200
        assert resp.json()["stdout"] == "123"

    @pytest.mark.asyncio
    async def test_get_execution_not_found(self, client):
        resp = await client.get(
            "/api/execute/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_execution(self, client):
        # Execute something first
        resp = await client.post(
            "/api/execute",
            json={
                "code": "print('done')",
                "language": "python",
                "timeout": 10,
            },
        )
        assert resp.status_code == 200
        exec_id = resp.json()["id"]

        # Try to stop (already completed)
        resp = await client.post(f"/api/execute/{exec_id}/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "already_completed"
