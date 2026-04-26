import asyncio

from backend.services.session_registry import session_registry


class ProcessSupervisor:
    async def stop(self, request_id: str) -> bool:
        session = await session_registry.get(request_id)
        if not session:
            return False
        if session.task and not session.task.done():
            session.task.cancel()
        if session.process and session.process.returncode is None:
            session.process.terminate()
            try:
                await asyncio.wait_for(session.process.wait(), timeout=2)
            except asyncio.TimeoutError:
                session.process.kill()
        await session_registry.pop(request_id)
        return True

    async def stop_all(self) -> int:
        count = 0
        for request_id in await session_registry.list_ids():
            stopped = await self.stop(request_id)
            if stopped:
                count += 1
        return count


process_supervisor = ProcessSupervisor()
