import asyncio
from dataclasses import dataclass


@dataclass
class ActiveSession:
    request_id: str
    task: asyncio.Task | None = None
    process: asyncio.subprocess.Process | None = None


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, ActiveSession] = {}
        self._lock = asyncio.Lock()

    async def register(self, session: ActiveSession) -> None:
        async with self._lock:
            self._sessions[session.request_id] = session

    async def pop(self, request_id: str) -> ActiveSession | None:
        async with self._lock:
            return self._sessions.pop(request_id, None)

    async def get(self, request_id: str) -> ActiveSession | None:
        async with self._lock:
            return self._sessions.get(request_id)

    async def list_ids(self) -> list[str]:
        async with self._lock:
            return list(self._sessions.keys())


session_registry = SessionRegistry()
