"""
Shared async retry with exponential backoff.
Used by: ALL services that call Ollama or external APIs.
"""
import asyncio
import logging
from typing import TypeVar, Callable, Any

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def async_retry(
    operation: Callable[..., Any],
    *args,
    retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    **kwargs,
) -> Any:
    """Execute an async operation with exponential backoff retry."""
    last_exception = None
    for attempt in range(retries):
        try:
            return await operation(*args, **kwargs)
        except exceptions as exc:
            last_exception = exc
            if attempt == retries - 1:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                "Retry %d/%d for %s after %.1fs: %s",
                attempt + 1, retries, operation.__name__, delay, exc,
            )
            await asyncio.sleep(delay)
    raise last_exception  # type: ignore
