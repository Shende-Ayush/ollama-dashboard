"""Resource limiter for code execution sandbox."""
from dataclasses import dataclass

from backend.features.code_execution.runtimes import get_runtime


@dataclass
class ResourceLimits:
    """Resource constraints for code execution."""

    timeout_seconds: int = 30
    memory_mb: int = 128
    cpu_count: float = 0.5
    pids_limit: int = 50
    disk_mb: int = 64
    network_enabled: bool = False


class ResourceLimiter:
    """Calculates and enforces resource limits for code execution."""

    MAX_TIMEOUT = 120
    MAX_MEMORY_MB = 512
    MAX_CPU = 2.0

    def calculate_limits(
        self, timeout: int, memory_mb: int, language: str
    ) -> ResourceLimits:
        """Calculate resource limits based on request and language defaults.

        Args:
            timeout: Requested timeout in seconds.
            memory_mb: Requested memory limit in MB.
            language: Programming language (for per-language defaults).

        Returns:
            ResourceLimits with clamped values.
        """
        runtime = get_runtime(language)

        # Use runtime defaults as baseline
        default_timeout = runtime["timeout"] if runtime else 30
        default_memory = runtime["memory_mb"] if runtime else 128

        # Clamp to maximums
        effective_timeout = min(
            max(timeout, 1), self.MAX_TIMEOUT, default_timeout * 4
        )
        effective_memory = min(
            max(memory_mb, 32), self.MAX_MEMORY_MB
        )

        # CPU allocation based on language complexity
        cpu_count = 0.5
        if language in ("go", "typescript"):
            cpu_count = 1.0

        return ResourceLimits(
            timeout_seconds=effective_timeout,
            memory_mb=effective_memory,
            cpu_count=min(cpu_count, self.MAX_CPU),
            pids_limit=50,
            disk_mb=64,
            network_enabled=False,
        )

    def to_docker_config(self, limits: ResourceLimits) -> dict:
        """Convert resource limits to Docker container config format.

        Args:
            limits: ResourceLimits to convert.

        Returns:
            Dictionary suitable for Docker container creation.
        """
        config = {
            "mem_limit": f"{limits.memory_mb}m",
            "memswap_limit": f"{limits.memory_mb}m",  # No swap
            "cpu_period": 100000,
            "cpu_quota": int(limits.cpu_count * 100000),
            "pids_limit": limits.pids_limit,
            "network_disabled": not limits.network_enabled,
            "read_only": True,
            "security_opt": ["no-new-privileges"],
        }
        return config
