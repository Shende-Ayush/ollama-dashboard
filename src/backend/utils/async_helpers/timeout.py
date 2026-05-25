"""
Shared async timeout context manager.
Used by: code_execution, agents, autonomous.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator


class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout."""
    def __init__(self, seconds: float):
        self.seconds = seconds
        super().__init__(f"Operation timed out after {seconds}s")


@asynccontextmanager
async def async_timeout(seconds: float) -> AsyncGenerator[None, None]:
    """Async context manager that raises TimeoutError after specified seconds."""
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        raise TimeoutError(seconds)
