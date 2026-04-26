from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.admin import router as admin_router
from backend.api.routes.analytics import router as analytics_router
from backend.api.routes.chat import router as chat_router
from backend.api.routes.commands import router as commands_router
from backend.api.routes.conversations import router as conversations_router
from backend.api.routes.metrics import router as metrics_router
from backend.api.routes.models import router as models_router
from backend.api.routes.requests import router as requests_router
from backend.api.routes.usage import router as usage_router
from backend.common.db.base import Base
from backend.common.db.session import engine
from backend.common.logging.middleware import CorrelationLoggingMiddleware
from backend.common.observability.prometheus import metrics_response

app = FastAPI(
    title="Ollama Dashboard API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationLoggingMiddleware)

@app.on_event("startup")
async def startup_event() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {"status": "ok"}

@app.get("/healthz", tags=["Health"])
async def healthz_check() -> dict:
    return {"status": "ok"}

@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    return metrics_response()

app.include_router(admin_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(commands_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(requests_router, prefix="/api")
app.include_router(usage_router, prefix="/api")
