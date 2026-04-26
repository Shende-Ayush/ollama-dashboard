"""
Chat router — no auth required.
"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.common.observability.prometheus import ACTIVE_STREAMS, TOKENS_IN, TOKENS_OUT
from backend.common.contracts.envelopes import StreamEvent
from backend.common.security.no_auth import require_api_key, resolve_user_from_token
from backend.common.security.prompt_guard import validate_prompt_content
from backend.features.chat.schemas import ChatStartRequest, ChatStartResponse, ChatStopRequest
from backend.features.conversations.models import Conversation, Message
from backend.features.llm.providers.ollama_provider import OllamaProvider
from backend.features.requests.models import RequestLog, StreamingSession
from backend.features.usage.models import ModelUsageLog
from backend.features.users.models import UserApiClient
from backend.services.context_manager import context_manager
from backend.services.process_supervisor import process_supervisor
from backend.services.session_registry import session_registry

router = APIRouter(tags=["chat"])
provider = OllamaProvider()
_requests: dict[str, ChatStartRequest] = {}
_stopped_requests: set[str] = set()


@router.post("/chat/start", response_model=ChatStartResponse)
async def chat_start(payload: ChatStartRequest) -> ChatStartResponse:
    request_id = uuid4().hex
    for msg in payload.messages:
        validate_prompt_content(msg.content)
    trimmed = context_manager.trim_messages(payload.messages, payload.context_tokens)
    _requests[request_id] = payload.model_copy(update={"messages": trimmed})
    return ChatStartResponse(request_id=request_id, status="ready")


@router.post("/chat/start-auth", response_model=ChatStartResponse)
async def chat_start_auth(
    payload: ChatStartRequest,
    current_user: UserApiClient = Depends(require_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> ChatStartResponse:
    request_id = uuid4().hex
    trimmed = context_manager.trim_messages(payload.messages, payload.context_tokens)
    token_input = sum(max(1, len(m.content) // 4) for m in trimmed)

    conversation: Conversation | None = None
    if payload.conversation_id:
        conversation = await session.get(Conversation, payload.conversation_id)
    if conversation is None:
        conversation = Conversation(
            user_id=current_user.id,
            title=(trimmed[0].content[:80] if trimmed else "New conversation"),
            model_name=payload.model,
            context_window=payload.context_tokens,
            total_tokens=0,
        )
        session.add(conversation)
        await session.flush()

    for msg in trimmed:
        session.add(Message(
            conversation_id=conversation.id,
            role=msg.role,
            content=msg.content,
            token_count=max(1, len(msg.content) // 4),
            latency_ms=0,
            model_name=payload.model,
            request_id=request_id,
        ))

    session.add(RequestLog(
        user_id=current_user.id,
        endpoint="/v1/chat/start-auth",
        method="POST",
        model_name=payload.model,
        status="ready",
        tokens_input=token_input,
        ip_address=None,
    ))
    session.add(StreamingSession(request_id=request_id, type="chat", status="ready"))
    await session.commit()

    _requests[request_id] = payload.model_copy(update={
        "messages": trimmed,
        "conversation_id": str(conversation.id),
    })
    TOKENS_IN.labels(model=payload.model).inc(token_input)
    ACTIVE_STREAMS.labels(type="chat").inc()
    return ChatStartResponse(
        request_id=request_id,
        status="ready",
        conversation_id=str(conversation.id),
    )


@router.get("/chat/stream")
async def chat_stream(
    request_id: str,
    token: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    # No token validation — open access
    req = _requests.get(request_id)
    if not req:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="request_id not found")

    async def event_gen():
        output_tokens = 0
        started = datetime.now(timezone.utc)
        was_interrupted = False
        try:
            async for token_chunk in provider.chat_stream(
                model=req.model,
                messages=[m.model_dump() for m in req.messages],
                options={"num_ctx": req.context_tokens},
            ):
                if request_id in _stopped_requests:
                    was_interrupted = True
                    yield f"data: {StreamEvent(event_type='stopped', request_id=request_id, payload={}).model_dump_json()}\n\n"
                    break
                yield f"data: {StreamEvent(event_type='token', request_id=request_id, payload={'token': token_chunk}).model_dump_json()}\n\n"
                output_tokens += max(1, len(token_chunk) // 4)
            yield f"data: {StreamEvent(event_type='done', request_id=request_id, payload={}).model_dump_json()}\n\n"
        finally:
            await session_registry.pop(request_id)
            _stopped_requests.discard(request_id)
            duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            TOKENS_OUT.labels(model=req.model).inc(output_tokens)
            try:
                result = await session.execute(
                    select(StreamingSession).where(StreamingSession.request_id == request_id)
                )
                stream_row = result.scalar_one_or_none()
                if stream_row:
                    stream_row.status = "done"
                    stream_row.ended_at = datetime.now(timezone.utc)
                    stream_row.interrupted = was_interrupted
                if req.conversation_id:
                    session.add(Message(
                        conversation_id=req.conversation_id,
                        role="assistant",
                        content="",
                        token_count=output_tokens,
                        latency_ms=duration_ms,
                        model_name=req.model,
                        request_id=request_id,
                    ))
                session.add(ModelUsageLog(
                    model_name=req.model,
                    request_id=request_id,
                    tokens_input=0,
                    tokens_output=output_tokens,
                    total_tokens=output_tokens,
                    duration_ms=duration_ms,
                    gpu_used=True,
                ))
                await session.commit()
            except Exception:
                pass

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/chat/stop")
async def chat_stop(payload: ChatStopRequest) -> dict:
    _stopped_requests.add(payload.request_id)
    stopped = await process_supervisor.stop(payload.request_id)
    return {"request_id": payload.request_id, "stopped": stopped}
