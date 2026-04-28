"""Conversations router — no auth required."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.common.security.no_auth import get_anonymous_user
from backend.features.conversations.models import Conversation, Message
from backend.schemas.pagination import paginate

router = APIRouter(tags=["conversations"])

_ANON = get_anonymous_user()


class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    is_archived: bool | None = None
    context_window: int | None = None


@router.get("/conversations")
async def get_conversations(
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=20, ge=1, le=100),
    archived: bool | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Conversation).order_by(Conversation.updated_at.desc())
    if archived is not None:
        stmt = stmt.where(Conversation.is_archived == archived)
    if q:
        stmt = stmt.where(Conversation.title.ilike(f"%{q}%"))
    total_result = await session.execute(select(func.count()).select_from(stmt.subquery()))
    total_records = total_result.scalar() or 0
    result = await session.execute(stmt.offset((pg_no - 1) * pg_size).limit(pg_size))
    rows = result.scalars().all()
    ids = [r.id for r in rows]
    message_counts: dict = {}
    if ids:
        counts = await session.execute(
            select(Message.conversation_id, func.count().label("message_count"))
            .where(Message.conversation_id.in_(ids))
            .group_by(Message.conversation_id)
        )
        message_counts = {row.conversation_id: int(row.message_count) for row in counts}
    items = [
        {
            "id": str(r.id), "title": r.title, "model_name": r.model_name,
            "context_window": r.context_window, "total_tokens": r.total_tokens,
            "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
            "is_archived": r.is_archived, "message_count": message_counts.get(r.id, 0),
        }
        for r in rows
    ]
    return {
        "page": {"pg_no": pg_no, "pg_size": pg_size, "total_records": total_records, "total_pg": (total_records + pg_size - 1) // pg_size if total_records else 0},
        "items": items,
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, session: AsyncSession = Depends(get_db_session)):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs_result = await session.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.asc())
    )
    messages = [
        {"id": str(m.id), "role": m.role, "content": m.content,
         "token_count": m.token_count, "model_name": m.model_name,
         "created_at": m.created_at.isoformat()}
        for m in msgs_result.scalars().all()
    ]
    return {
        "id": str(conv.id), "title": conv.title, "model_name": conv.model_name,
        "context_window": conv.context_window, "total_tokens": conv.total_tokens,
        "created_at": conv.created_at.isoformat(), "updated_at": conv.updated_at.isoformat(),
        "is_archived": conv.is_archived, "messages": messages,
    }


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if payload.title is not None:
        conv.title = payload.title
    if payload.is_archived is not None:
        conv.is_archived = payload.is_archived
    if payload.context_window is not None:
        conv.context_window = payload.context_window
    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"id": str(conv.id), "updated": True}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, session: AsyncSession = Depends(get_db_session)):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = await session.execute(select(Message).where(Message.conversation_id == conv.id))
    for msg in msgs.scalars().all():
        await session.delete(msg)
    await session.delete(conv)
    await session.commit()
    return {"deleted": True, "id": conversation_id}


@router.get("/messages")
async def get_messages(
    conversation_id: str,
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    base = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    total_result = await session.execute(select(func.count()).select_from(select(Message).where(Message.conversation_id == conversation_id).subquery()))
    total_records = total_result.scalar() or 0
    result = await session.execute(base.offset((pg_no - 1) * pg_size).limit(pg_size))
    rows = result.scalars().all()
    items = [
        {"id": str(r.id), "role": r.role, "content": r.content,
         "token_count": r.token_count, "model_name": r.model_name,
         "request_id": r.request_id, "created_at": r.created_at.isoformat()}
        for r in rows
    ]
    return {
        "page": {"pg_no": pg_no, "pg_size": pg_size, "total_records": total_records, "total_pg": (total_records + pg_size - 1) // pg_size if total_records else 0},
        "items": items,
    }
