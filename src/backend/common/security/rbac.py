from fastapi import HTTPException, status

from backend.features.users.models import UserApiClient


def require_role(user: UserApiClient, allowed: set[str]) -> None:
    if user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role permissions")
