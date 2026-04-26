from contextvars import ContextVar
from uuid import uuid4


correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    return correlation_id_ctx.get() or ""


def set_correlation_id(value: str | None) -> str:
    correlation_id = value or uuid4().hex
    correlation_id_ctx.set(correlation_id)
    return correlation_id
