"""Admin router — stubs out user management (auth removed)."""
from fastapi import APIRouter
router = APIRouter(tags=["admin"])

@router.get("/admin/status")
async def admin_status():
    return {"status": "ok", "auth": "disabled", "note": "API key auth is disabled. Re-enable in common/security/api_key.py when ready."}
