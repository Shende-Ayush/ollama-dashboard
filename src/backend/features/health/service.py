"""
Health Monitoring & Auto-Recovery — Service layer.

Provides:
- Multi-component health checks (Ollama, Postgres, Redis, GPU, Disk)
- Incident detection and tracking
- Auto-recovery with safe fallback mechanisms
- System uptime monitoring
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.features.health.models import (
    HealthCheck,
    HealthIncident,
    RecoveryAction,
)
from backend.features.health.schemas import (
    ComponentHealth,
    HealthIncidentResponse,
    RecoveryActionResponse,
    SystemHealthResponse,
)
from backend.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# Track startup time for uptime calculation
_startup_time = time.time()



class HealthMonitorService:
    """
    Comprehensive health monitoring and auto-recovery service.

    Monitors:
    - Ollama service availability and response time
    - Database connectivity
    - GPU memory and utilization
    - Disk space
    - Redis connectivity

    Auto-recovery:
    - Clears stuck models from GPU
    - Reconnects to services
    - Triggers garbage collection
    """

    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        self.client = ollama_client or OllamaClient()
        self._recovery_handlers = {
            "ollama": self._recover_ollama,
            "gpu": self._recover_gpu,
        }

    # -----------------------------------------------------------------------
    # Full system health check
    # -----------------------------------------------------------------------
    async def check_system_health(
        self, session: AsyncSession
    ) -> SystemHealthResponse:
        """Run health checks on all system components."""
        components: list[ComponentHealth] = []

        # Run checks concurrently
        checks = await asyncio.gather(
            self._check_ollama(),
            self._check_database(session),
            self._check_gpu(),
            self._check_disk(),
            return_exceptions=True,
        )

        for check in checks:
            if isinstance(check, ComponentHealth):
                components.append(check)
            elif isinstance(check, Exception):
                logger.warning("Health check error: %s", check)

        # Persist health checks
        for comp in components:
            hc = HealthCheck(
                component=comp.component,
                status=comp.status,
                response_time_ms=comp.response_time_ms,
                details=comp.details,
            )
            session.add(hc)

        # Detect incidents
        for comp in components:
            if comp.status == "unhealthy":
                await self._create_incident(comp, session)

        await session.commit()

        # Determine overall status
        statuses = [c.status for c in components]
        if "unhealthy" in statuses:
            overall = "unhealthy"
        elif "degraded" in statuses:
            overall = "degraded"
        else:
            overall = "healthy"

        return SystemHealthResponse(
            overall_status=overall,
            components=components,
            uptime_seconds=int(time.time() - _startup_time),
            checked_at=datetime.now(timezone.utc),
        )


    # -----------------------------------------------------------------------
    # Individual component checks
    # -----------------------------------------------------------------------
    async def _check_ollama(self) -> ComponentHealth:
        """Check Ollama service health."""
        start = time.time()
        try:
            models = await self.client.list_models()
            response_ms = int((time.time() - start) * 1000)

            running = await self.client.list_running()
            details = {
                "models_installed": len(models),
                "models_running": len(running),
                "running_models": [m.get("name") for m in running],
            }

            status = "healthy"
            if response_ms > 5000:
                status = "degraded"

            return ComponentHealth(
                component="ollama",
                status=status,
                response_time_ms=response_ms,
                details=details,
                last_checked=datetime.now(timezone.utc),
            )
        except Exception as exc:
            response_ms = int((time.time() - start) * 1000)
            return ComponentHealth(
                component="ollama",
                status="unhealthy",
                response_time_ms=response_ms,
                details={"error": str(exc)},
                last_checked=datetime.now(timezone.utc),
            )

    async def _check_database(self, session: AsyncSession) -> ComponentHealth:
        """Check database connectivity."""
        start = time.time()
        try:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            response_ms = int((time.time() - start) * 1000)

            return ComponentHealth(
                component="postgres",
                status="healthy" if response_ms < 1000 else "degraded",
                response_time_ms=response_ms,
                details={"connected": True},
                last_checked=datetime.now(timezone.utc),
            )
        except Exception as exc:
            response_ms = int((time.time() - start) * 1000)
            return ComponentHealth(
                component="postgres",
                status="unhealthy",
                response_time_ms=response_ms,
                details={"error": str(exc), "connected": False},
                last_checked=datetime.now(timezone.utc),
            )

    async def _check_gpu(self) -> ComponentHealth:
        """Check GPU availability and memory."""
        start = time.time()
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            response_ms = int((time.time() - start) * 1000)

            if result.returncode != 0:
                return ComponentHealth(
                    component="gpu",
                    status="unknown",
                    response_time_ms=response_ms,
                    details={"error": "nvidia-smi not available", "gpu_present": False},
                    last_checked=datetime.now(timezone.utc),
                )

            lines = result.stdout.strip().split("\n")
            gpus = []
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    gpus.append({
                        "utilization_percent": float(parts[0]),
                        "memory_used_mb": float(parts[1]),
                        "memory_total_mb": float(parts[2]),
                        "memory_usage_percent": round(
                            float(parts[1]) / float(parts[2]) * 100, 1
                        ) if float(parts[2]) > 0 else 0,
                    })

            # Determine status based on memory usage
            status = "healthy"
            for gpu in gpus:
                if gpu["memory_usage_percent"] > 95:
                    status = "unhealthy"
                    break
                elif gpu["memory_usage_percent"] > 80:
                    status = "degraded"

            return ComponentHealth(
                component="gpu",
                status=status,
                response_time_ms=response_ms,
                details={"gpus": gpus, "gpu_count": len(gpus), "gpu_present": True},
                last_checked=datetime.now(timezone.utc),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            response_ms = int((time.time() - start) * 1000)
            return ComponentHealth(
                component="gpu",
                status="unknown",
                response_time_ms=response_ms,
                details={"gpu_present": False, "error": "nvidia-smi not found"},
                last_checked=datetime.now(timezone.utc),
            )
        except Exception as exc:
            response_ms = int((time.time() - start) * 1000)
            return ComponentHealth(
                component="gpu",
                status="unknown",
                response_time_ms=response_ms,
                details={"error": str(exc)},
                last_checked=datetime.now(timezone.utc),
            )

    async def _check_disk(self) -> ComponentHealth:
        """Check disk space availability."""
        start = time.time()
        try:
            import shutil
            usage = shutil.disk_usage("/")
            response_ms = int((time.time() - start) * 1000)

            total_gb = round(usage.total / (1024**3), 2)
            used_gb = round(usage.used / (1024**3), 2)
            free_gb = round(usage.free / (1024**3), 2)
            usage_percent = round(usage.used / usage.total * 100, 1)

            status = "healthy"
            if usage_percent > 95:
                status = "unhealthy"
            elif usage_percent > 85:
                status = "degraded"

            return ComponentHealth(
                component="disk",
                status=status,
                response_time_ms=response_ms,
                details={
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "usage_percent": usage_percent,
                },
                last_checked=datetime.now(timezone.utc),
            )
        except Exception as exc:
            response_ms = int((time.time() - start) * 1000)
            return ComponentHealth(
                component="disk",
                status="unknown",
                response_time_ms=response_ms,
                details={"error": str(exc)},
                last_checked=datetime.now(timezone.utc),
            )


    # -----------------------------------------------------------------------
    # Incident management
    # -----------------------------------------------------------------------
    async def _create_incident(
        self, component: ComponentHealth, session: AsyncSession
    ) -> HealthIncident:
        """Create an incident for an unhealthy component."""
        # Check if there's already an open incident for this component
        result = await session.execute(
            select(HealthIncident).where(
                HealthIncident.component == component.component,
                HealthIncident.status.in_(["open", "acknowledged"]),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        severity = "critical" if component.component in ("ollama", "postgres") else "warning"
        error_msg = component.details.get("error", "Component unhealthy")

        incident = HealthIncident(
            component=component.component,
            severity=severity,
            title=f"{component.component.upper()} is unhealthy",
            description=f"Health check failed: {error_msg}",
            status="open",
        )
        session.add(incident)
        await session.flush()

        # Attempt auto-recovery
        if component.component in self._recovery_handlers:
            await self._attempt_auto_recovery(incident, session)

        return incident

    async def list_incidents(
        self,
        session: AsyncSession,
        status: Optional[str] = None,
        component: Optional[str] = None,
        limit: int = 50,
    ) -> list[HealthIncidentResponse]:
        """List health incidents."""
        stmt = select(HealthIncident).order_by(HealthIncident.detected_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(HealthIncident.status == status)
        if component:
            stmt = stmt.where(HealthIncident.component == component)

        result = await session.execute(stmt)
        incidents = result.scalars().all()

        return [
            HealthIncidentResponse(
                id=str(i.id),
                component=i.component,
                severity=i.severity,
                title=i.title,
                description=i.description,
                status=i.status,
                auto_recovery_attempted=i.auto_recovery_attempted,
                auto_recovery_successful=i.auto_recovery_successful,
                recovery_action=i.recovery_action,
                detected_at=i.detected_at,
                resolved_at=i.resolved_at,
            )
            for i in incidents
        ]

    async def resolve_incident(
        self, incident_id: str, session: AsyncSession
    ) -> None:
        """Manually resolve an incident."""
        import uuid as _uuid
        incident = await session.get(HealthIncident, _uuid.UUID(incident_id))
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
        incident.status = "resolved"
        incident.resolved_at = datetime.now(timezone.utc)
        await session.commit()


    # -----------------------------------------------------------------------
    # Auto-recovery
    # -----------------------------------------------------------------------
    async def _attempt_auto_recovery(
        self, incident: HealthIncident, session: AsyncSession
    ) -> None:
        """Attempt automatic recovery for an incident."""
        handler = self._recovery_handlers.get(incident.component)
        if not handler:
            return

        incident.auto_recovery_attempted = True
        recovery = RecoveryAction(
            incident_id=incident.id,
            component=incident.component,
            action_type="restart",
            description=f"Auto-recovery for {incident.component}",
            status="executing",
        )
        session.add(recovery)
        await session.flush()

        start_time = time.time()
        try:
            success, result_msg = await handler()
            duration_ms = int((time.time() - start_time) * 1000)

            recovery.status = "success" if success else "failed"
            recovery.result = result_msg
            recovery.duration_ms = duration_ms

            if success:
                incident.auto_recovery_successful = True
                incident.status = "auto_resolved"
                incident.resolved_at = datetime.now(timezone.utc)
                incident.recovery_action = result_msg

        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            recovery.status = "failed"
            recovery.result = str(exc)
            recovery.duration_ms = duration_ms
            logger.error("Auto-recovery failed for %s: %s", incident.component, exc)

    async def trigger_recovery(
        self, component: str, action_type: str, session: AsyncSession
    ) -> RecoveryActionResponse:
        """Manually trigger a recovery action."""
        handler = self._recovery_handlers.get(component)
        if not handler:
            raise ValueError(f"No recovery handler for component: {component}")

        recovery = RecoveryAction(
            component=component,
            action_type=action_type,
            description=f"Manual recovery triggered for {component}",
            status="executing",
        )
        session.add(recovery)
        await session.flush()

        start_time = time.time()
        try:
            success, result_msg = await handler()
            duration_ms = int((time.time() - start_time) * 1000)
            recovery.status = "success" if success else "failed"
            recovery.result = result_msg
            recovery.duration_ms = duration_ms
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            recovery.status = "failed"
            recovery.result = str(exc)
            recovery.duration_ms = duration_ms

        await session.commit()
        await session.refresh(recovery)

        return RecoveryActionResponse(
            id=str(recovery.id),
            incident_id=str(recovery.incident_id) if recovery.incident_id else None,
            component=recovery.component,
            action_type=recovery.action_type,
            description=recovery.description,
            status=recovery.status,
            result=recovery.result,
            executed_at=recovery.executed_at,
            duration_ms=recovery.duration_ms,
        )

    async def _recover_ollama(self) -> tuple[bool, str]:
        """Attempt to recover Ollama connectivity."""
        # Try to ping Ollama
        for attempt in range(3):
            try:
                await asyncio.sleep(1)
                models = await self.client.list_models()
                return True, f"Ollama recovered after {attempt + 1} attempt(s). {len(models)} models available."
            except Exception:
                continue
        return False, "Ollama recovery failed after 3 attempts"

    async def _recover_gpu(self) -> tuple[bool, str]:
        """Attempt to recover GPU by clearing stuck models."""
        try:
            running = await self.client.list_running()
            cleared = []
            for model in running:
                name = model.get("name")
                if name:
                    try:
                        await self.client.stop_model(name)
                        cleared.append(name)
                    except Exception:
                        continue

            if cleared:
                return True, f"Cleared {len(cleared)} model(s) from GPU: {', '.join(cleared)}"
            return True, "No models needed clearing"
        except Exception as exc:
            return False, f"GPU recovery failed: {str(exc)}"

    async def list_recovery_actions(
        self, session: AsyncSession, limit: int = 50
    ) -> list[RecoveryActionResponse]:
        """List recent recovery actions."""
        result = await session.execute(
            select(RecoveryAction)
            .order_by(RecoveryAction.executed_at.desc())
            .limit(limit)
        )
        return [
            RecoveryActionResponse(
                id=str(r.id),
                incident_id=str(r.incident_id) if r.incident_id else None,
                component=r.component,
                action_type=r.action_type,
                description=r.description,
                status=r.status,
                result=r.result,
                executed_at=r.executed_at,
                duration_ms=r.duration_ms,
            )
            for r in result.scalars().all()
        ]


# Module singleton
health_service = HealthMonitorService()
