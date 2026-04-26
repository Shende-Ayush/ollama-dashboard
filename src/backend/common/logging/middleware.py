"""Request correlation + logging middleware — no auth dependency."""
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.common.db.session import SessionLocal
from backend.common.logging.correlation import set_correlation_id
from backend.common.observability.prometheus import REQUEST_COUNT, REQUEST_LATENCY
from backend.features.requests.models import RequestLog

logger = logging.getLogger("api")

# Paths that are too noisy / useless to log
_SKIP_PATHS = {"/healthz", "/readyz", "/metrics", "/docs", "/redoc", "/openapi.json"}


class CorrelationLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started_at = time.perf_counter()
        correlation_id = set_correlation_id(request.headers.get("x-correlation-id"))
        request.state.correlation_id = correlation_id
        request.state.request_log_id = None

        # Skip noisy health/metrics paths from DB logging
        if request.url.path not in _SKIP_PATHS:
            try:
                async with SessionLocal() as session:
                    req_log = RequestLog(
                        endpoint=request.url.path,
                        method=request.method,
                        status="started",
                        ip_address=request.client.host if request.client else None,
                    )
                    session.add(req_log)
                    await session.flush()
                    request.state.request_log_id = req_log.id
                    await session.commit()
            except Exception:
                logger.exception("Failed to persist request start log")

        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

        REQUEST_COUNT.labels(method=request.method, path=request.url.path, status=str(response.status_code)).inc()
        REQUEST_LATENCY.labels(method=request.method, path=request.url.path).observe(duration_ms / 1000.0)
        response.headers["x-correlation-id"] = correlation_id

        if request.url.path not in _SKIP_PATHS:
            try:
                async with SessionLocal() as session:
                    if request.state.request_log_id:
                        req_log = await session.get(RequestLog, request.state.request_log_id)
                        if req_log:
                            req_log.status = "ok" if response.status_code < 400 else "error"
                            req_log.duration_ms = int(duration_ms)
                            await session.commit()
            except Exception:
                logger.exception("Failed to persist request completion log")

        logger.info(
            "request completed",
            extra={
                "request_id": correlation_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
