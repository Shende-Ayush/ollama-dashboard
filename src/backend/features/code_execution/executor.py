"""Code executor — runs code in isolated subprocesses.

Production: Docker containers. Dev/test: subprocess with limits.
The interface is designed so Docker can be swapped in later.
"""
import asyncio
import os
import tempfile
import time
from dataclasses import dataclass

from backend.features.code_execution.limiter import ResourceLimits
from backend.features.code_execution.runtimes import get_runtime


@dataclass
class ExecutionResult:
    """Result of a code execution."""

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    memory_used_mb: float
    timed_out: bool = False


class CodeExecutor:
    """Executes code in an isolated subprocess.

    Production: Docker containers. Dev/test: subprocess with limits.
    """

    async def run(
        self,
        code: str,
        language: str,
        limits: ResourceLimits,
        stdin: str = "",
    ) -> ExecutionResult:
        """Execute code and return results.

        Args:
            code: Source code to execute.
            language: Programming language.
            limits: Resource constraints.
            stdin: Standard input for the program.

        Returns:
            ExecutionResult with output and metrics.
        """
        runtime = get_runtime(language)
        if not runtime:
            return ExecutionResult(
                stdout="",
                stderr=f"Unsupported language: {language}",
                exit_code=1,
                duration_ms=0,
                memory_used_mb=0.0,
                timed_out=False,
            )

        # For Go, we need to write to a file; for others, use -c/-e flags
        if language == "go":
            return await self._run_file_based(code, runtime, limits, stdin)
        else:
            return await self._run_inline(code, runtime, limits, stdin)

    async def _run_inline(
        self,
        code: str,
        runtime: dict,
        limits: ResourceLimits,
        stdin: str,
    ) -> ExecutionResult:
        """Run code using inline execution (e.g., python -c 'code')."""
        cmd = runtime["cmd"] + [code]
        return await self._execute_subprocess(cmd, limits, stdin)

    async def _run_file_based(
        self,
        code: str,
        runtime: dict,
        limits: ResourceLimits,
        stdin: str,
    ) -> ExecutionResult:
        """Run code by writing to a temp file first (e.g., Go)."""
        extension = runtime["extension"]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=extension, delete=False
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Replace /tmp/main.go placeholder with actual temp path
            cmd = [
                part.replace("/tmp/main.go", temp_path)
                for part in runtime["cmd"]
            ]
            return await self._execute_subprocess(cmd, limits, stdin)
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def _execute_subprocess(
        self,
        cmd: list[str],
        limits: ResourceLimits,
        stdin: str,
    ) -> ExecutionResult:
        """Execute a command as subprocess with timeout enforcement."""
        start_time = time.time()
        timed_out = False

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(
                        input=stdin.encode() if stdin else None
                    ),
                    timeout=limits.timeout_seconds,
                )
            except asyncio.TimeoutError:
                timed_out = True
                process.kill()
                await process.wait()
                stdout_bytes = b""
                stderr_bytes = b"Execution timed out"

            duration_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace").rstrip(),
                stderr=stderr_bytes.decode("utf-8", errors="replace").rstrip(),
                exit_code=process.returncode if not timed_out else -1,
                duration_ms=duration_ms,
                memory_used_mb=0.0,  # Subprocess-based: no memory tracking
                timed_out=timed_out,
            )

        except FileNotFoundError:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                stdout="",
                stderr=f"Runtime not found: {cmd[0]}",
                exit_code=127,
                duration_ms=duration_ms,
                memory_used_mb=0.0,
                timed_out=False,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                stdout="",
                stderr=f"Execution error: {str(exc)}",
                exit_code=1,
                duration_ms=duration_ms,
                memory_used_mb=0.0,
                timed_out=False,
            )
