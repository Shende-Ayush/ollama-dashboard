from fastapi.middleware.cors import CORSMiddleware
    app = FastAPI(
        docs_url="/docs",
    )

    app.add_middleware(
        CORSMiddleware,
    )

# ----------------------------------------------------------------------
# Simple health‑check endpoint – returns 200 if the service is up.
# ----------------------------------------------------------------------
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Very lightweight endpoint used by Docker `HEALTHCHECK` and CI.
    Returns a static JSON payload; you can extend it to include DB
    connectivity checks later if needed.
    """
    return {"status": "ok"}

# ----------------------------------------------------------------------
# Import and include your API routers after the health endpoint so the
# docs show it first.
# ----------------------------------------------------------------------
ORIGINAL CODE:
# app.include_router(chat_router, prefix="/api/v1")
# app.include_router(models_router, prefix="/api/v1")
Thus output file contents as per suggested edit, not original. Let's output the suggested code only.```python
# Example:
# from src.backend.api import chat_router, models_router
# app.include_router(chat_router, prefix="/api/v1")
# app.include_router(models_router, prefix="/api/v1")