"""
Chat router — no auth required.
"""
from datetime import datetime, timezone
from uuid import uuid4

import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query
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
from backend.services.token_counter import token_counter

router = APIRouter(tags=["chat"])
provider = OllamaProvider()
_requests: dict[str, ChatStartRequest] = {}
_request_input_tokens: dict[str, int] = {}
_stopped_requests: set[str] = set()


async def ensure_model_available(model_name: str) -> None:
    try:
        installed_models = await provider.list_models()
    except Exception as exc:
        logger.warning("Unable to verify Ollama model availability: %s", exc)
        raise HTTPException(status_code=503, detail="Ollama is not reachable. Start Ollama and try again.") from exc

    installed_names = {model.get("name") for model in installed_models if model.get("name")}
    if model_name not in installed_names:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' is not installed. Pull or select an installed model before chatting.",
        )


def conversation_title_from_prompt(prompt: str) -> str:
    words = " ".join(prompt.strip().split())
    if not words:
        return "New conversation"
    title = words[:72].rstrip(" .,;:-")
    return title or "New conversation"


@router.post("/chat/start", response_model=ChatStartResponse)
async def chat_start(payload: ChatStartRequest) -> ChatStartResponse:
    request_id = uuid4().hex
    for msg in payload.messages:
        validate_prompt_content(msg.content)
    await ensure_model_available(payload.model)
    trimmed = context_manager.trim_messages(payload.messages, payload.context_tokens)
    _request_input_tokens[request_id] = token_counter.count_messages(trimmed)
    _requests[request_id] = payload.model_copy(update={"messages": trimmed})
    return ChatStartResponse(
        request_id=request_id,
        status="ready",
        conversation_id=None,
    )


@router.post("/chat/start-auth", response_model=ChatStartResponse)
async def chat_start_auth(
    payload: ChatStartRequest,
    current_user: UserApiClient = Depends(require_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> ChatStartResponse:
    request_id = uuid4().hex
    for msg in payload.messages:
        validate_prompt_content(msg.content)
    await ensure_model_available(payload.model)
    trimmed = context_manager.trim_messages(payload.messages, payload.context_tokens)
    token_input = token_counter.count_messages(trimmed)

    conversation: Conversation | None = None
    existing_message_count = 0
    if payload.conversation_id:
        conversation = await session.get(Conversation, payload.conversation_id)
        if conversation:
            count_result = await session.execute(
                select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())
            )
            existing_message_count = len(count_result.scalars().all())
    if conversation is None:
        conversation = Conversation(
            user_id=current_user.id,
            title=conversation_title_from_prompt(trimmed[0].content if trimmed else ""),
            model_name=payload.model,
            context_window=payload.context_tokens,
            total_tokens=0,
        )
        try:
            session.add(conversation)
            await session.flush()
        except Exception as e:
            logger.error(f"Error adding conversation: {e}")
            raise

    try:
        new_messages = payload.messages[existing_message_count:] if existing_message_count else payload.messages
        if not new_messages and payload.messages:
            new_messages = [payload.messages[-1]]
        for msg in new_messages:
            msg_tokens = token_counter.count_text(msg.content)
            session.add(Message(
                conversation_id=conversation.id,
                role=msg.role,
                content=msg.content,
                token_count=msg_tokens,
                latency_ms=0,
                model_name=payload.model,
                request_id=request_id,
            ))
            conversation.total_tokens += msg_tokens

        conversation.updated_at = datetime.now(timezone.utc)
        conversation.context_window = payload.context_tokens
        conversation.model_name = payload.model
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

        conversation_id = str(conversation.id)
        await session.commit()
    except Exception as e:
        logger.error(f"Error committing session: {e}")
        raise

    try:
        _requests[request_id] = payload.model_copy(update={
            "messages": trimmed,
            "conversation_id": conversation_id,
        })
        _request_input_tokens[request_id] = token_input
        TOKENS_IN.labels(model=payload.model).inc(token_input)
        ACTIVE_STREAMS.labels(type="chat").inc()
    except Exception as e:
        logger.error(f"Error updating metrics or requests: {e}")
        raise

    return ChatStartResponse(
        request_id=request_id,
        status="ready",
        conversation_id=conversation_id,
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
        raise HTTPException(status_code=404, detail="request_id not found")

    async def event_gen():
        output_tokens = 0
        started = datetime.now(timezone.utc)
        was_interrupted = False
        assistant_content = ""
        stream_status = "done"
        stream_error: str | None = None
        try:
            async for token_chunk in provider.chat_stream(
                model=req.model,
                messages=[m.model_dump() for m in req.messages],
                options={"num_ctx": req.context_tokens},
            ):
                if request_id in _stopped_requests:
                    was_interrupted = True
                    stream_status = "stopped"
                    yield f"data: {StreamEvent(event_type='stopped', request_id=request_id, payload={}).model_dump_json()}\n\n"
                    break
                assistant_content += token_chunk
                yield f"data: {StreamEvent(event_type='token', request_id=request_id, payload={'token': token_chunk}).model_dump_json()}\n\n"
                output_tokens += max(1, len(token_chunk) // 4)
            if not was_interrupted:
                yield f"data: {StreamEvent(event_type='done', request_id=request_id, payload={}).model_dump_json()}\n\n"
        except Exception as exc:
            logger.exception("Chat stream failed for request %s", request_id)
            stream_status = "error"
            stream_error = str(exc)
            yield f"data: {StreamEvent(event_type='error', request_id=request_id, payload={'message': stream_error}).model_dump_json()}\n\n"
        finally:
            await session_registry.pop(request_id)
            _requests.pop(request_id, None)
            input_tokens = _request_input_tokens.pop(request_id, 0)
            _stopped_requests.discard(request_id)
            duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            TOKENS_OUT.labels(model=req.model).inc(output_tokens)
            try:
                result = await session.execute(
                    select(StreamingSession).where(StreamingSession.request_id == request_id)
                )
                stream_row = result.scalar_one_or_none()
                if stream_row:
                    stream_row.status = stream_status
                    stream_row.ended_at = datetime.now(timezone.utc)
                    stream_row.interrupted = was_interrupted
                if req.conversation_id:
                    session.add(Message(
                        conversation_id=req.conversation_id,
                        role="assistant",
                        content=assistant_content,
                        token_count=output_tokens,
                        latency_ms=duration_ms,
                        model_name=req.model,
                        request_id=request_id,
                    ))
                    conv = await session.get(Conversation, req.conversation_id)
                    if conv:
                        conv.total_tokens += output_tokens
                        conv.updated_at = datetime.now(timezone.utc)
                session.add(ModelUsageLog(
                    model_name=req.model,
                    request_id=request_id,
                    tokens_input=input_tokens,
                    tokens_output=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    duration_ms=duration_ms,
                    gpu_used=True,
                ))
                await session.commit()
            except Exception as exc:
                logger.warning("Failed to persist chat stream result for %s: %s", request_id, exc)
                await session.rollback()

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/chat/stop")
async def chat_stop(payload: ChatStopRequest) -> dict:
    _stopped_requests.add(payload.request_id)
    stopped = await process_supervisor.stop(payload.request_id)
    return {"request_id": payload.request_id, "stopped": stopped}
