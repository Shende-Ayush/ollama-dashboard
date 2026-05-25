"""Code execution service — main orchestrator for sandbox execution."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.features.code_execution.executor import CodeExecutor
from backend.features.code_execution.guard import ExecutionGuard
from backend.features.code_execution.limiter import ResourceLimiter
from backend.features.code_execution.models import CodeExecution
from backend.features.code_execution.runtimes import (
    is_supported,
    list_runtimes,
)
from backend.features.code_execution.schemas import (
    ExecuteRequest,
    ExecutionResponse,
    RuntimeInfo,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class ExecutionService:
    """Orchestrates code execution with security validation and resource limits."""

    def __init__(self) -> None:
        self.guard = ExecutionGuard()
        self.limiter = ResourceLimiter()
        self.executor = CodeExecutor()

    async def execute(
        self, request: ExecuteRequest, session: AsyncSession
    ) -> ExecutionResponse:
        """Execute code in a sandboxed environment.

        Steps:
        1. Validate language supported
        2. Run security guard
        3. Calculate resource limits
        4. Create DB record (status=queued)
        5. Execute in subprocess
        6. Capture stdout/stderr
        7. Update DB record with result
        8. Return response

        Args:
            request: Execution request with code and parameters.
            session: Database session.

        Returns:
            ExecutionResponse with execution results.

        Raises:
            ValueError: If language is unsupported or code fails validation.
        """
        language = request.language.lower()

        # 1. Validate language
        if not is_supported(language):
            raise ValueError(f"Unsupported language: {language}")

        # 2. Security validation
        is_safe, violations = self.guard.is_execution_allowed(
            request.code, language
        )
        if not is_safe:
            raise ValueError(
                f"Code failed security validation: {'; '.join(violations)}"
            )

        # 3. Calculate resource limits
        limits = self.limiter.calculate_limits(
            timeout=request.timeout,
            memory_mb=request.memory_mb,
            language=language,
        )

        # 4. Create DB record
        execution = CodeExecution(
            id=uuid.uuid4(),
            language=language,
            code=request.code,
            stdin=request.stdin,
            status="queued",
        )
        session.add(execution)
        await session.flush()

        # 5. Update status to running
        execution.status = "running"
        await session.flush()

        # 6. Execute code
        result = await self.executor.run(
            code=request.code,
            language=language,
            limits=limits,
            stdin=request.stdin or "",
        )

        # 7. Update DB record
        execution.stdout = result.stdout
        execution.stderr = result.stderr
        execution.exit_code = result.exit_code
        execution.duration_ms = result.duration_ms
        execution.memory_used_mb = result.memory_used_mb
        execution.completed_at = datetime.now(timezone.utc)

        if result.timed_out:
            execution.status = "timeout"
        elif result.exit_code == 0:
            execution.status = "completed"
        else:
            execution.status = "failed"

        await session.commit()

        # 8. Return response
        return ExecutionResponse(
            id=execution.id,
            language=execution.language,
            status=execution.status,
            stdout=execution.stdout,
            stderr=execution.stderr,
            exit_code=execution.exit_code,
            duration_ms=execution.duration_ms,
            memory_used_mb=execution.memory_used_mb,
            created_at=execution.created_at,
            completed_at=execution.completed_at,
        )

    async def get_execution(
        self, execution_id: str, session: AsyncSession
    ) -> ExecutionResponse:
        """Get execution result by ID.

        Args:
            execution_id: UUID of the execution record.
            session: Database session.

        Returns:
            ExecutionResponse with execution details.

        Raises:
            ValueError: If execution not found.
        """
        try:
            exec_uuid = uuid.UUID(execution_id)
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid execution ID: {execution_id}")

        result = await session.execute(
            select(CodeExecution).where(CodeExecution.id == exec_uuid)
        )
        execution = result.scalar_one_or_none()

        if not execution:
            raise ValueError(f"Execution not found: {execution_id}")

        return ExecutionResponse(
            id=execution.id,
            language=execution.language,
            status=execution.status,
            stdout=execution.stdout,
            stderr=execution.stderr,
            exit_code=execution.exit_code,
            duration_ms=execution.duration_ms,
            memory_used_mb=execution.memory_used_mb,
            created_at=execution.created_at,
            completed_at=execution.completed_at,
        )

    async def stop_execution(
        self, execution_id: str, session: AsyncSession
    ) -> dict:
        """Stop a running execution.

        Args:
            execution_id: UUID of the execution to stop.
            session: Database session.

        Returns:
            Status dictionary.

        Raises:
            ValueError: If execution not found or not running.
        """
        try:
            exec_uuid = uuid.UUID(execution_id)
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid execution ID: {execution_id}")

        result = await session.execute(
            select(CodeExecution).where(CodeExecution.id == exec_uuid)
        )
        execution = result.scalar_one_or_none()

        if not execution:
            raise ValueError(f"Execution not found: {execution_id}")

        if execution.status not in ("queued", "running"):
            return {"status": "already_completed", "execution_status": execution.status}

        execution.status = "cancelled"
        execution.completed_at = datetime.now(timezone.utc)
        await session.commit()

        return {"status": "cancelled", "execution_id": str(execution.id)}

    async def validate_code(
        self, code: str, language: str
    ) -> ValidationResult:
        """Validate code safety without executing.

        Args:
            code: Source code to validate.
            language: Programming language.

        Returns:
            ValidationResult with safety assessment.
        """
        scan_result = self.guard.validate(code, language)
        return self.guard.to_validation_result(scan_result)

    async def list_runtimes(self) -> list[RuntimeInfo]:
        """List all supported runtime environments.

        Returns:
            List of RuntimeInfo objects.
        """
        return list_runtimes()


# Module-level singleton
execution_service = ExecutionService()
