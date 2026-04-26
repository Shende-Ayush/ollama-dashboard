"""Commands router — no auth required."""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import SessionLocal, get_db_session
from backend.common.security.no_auth import get_anonymous_user
from backend.services.command_guard import validate_command
from backend.services.process_supervisor import process_supervisor
from backend.schemas.pagination import paginate
from backend.features.commands.models import CommandHistory
from backend.features.requests.models import StreamingSession
from backend.services.session_registry import ActiveSession, session_registry

router = APIRouter(tags=["commands"])


@router.get("/commands/history")
async def commands_history(
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(CommandHistory).order_by(CommandHistory.started_at.desc())
    if status:
        stmt = stmt.where(CommandHistory.status == status)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    items = [
        {"id": str(r.id), "command": r.command, "command_type": r.command_type,
         "status": r.status, "output": r.output, "duration_ms": r.duration_ms,
         "started_at": r.started_at.isoformat(),
         "completed_at": r.completed_at.isoformat() if r.completed_at else None}
        for r in rows
    ]
    return paginate(items, pg_no=pg_no, pg_size=pg_size).model_dump()


@router.get("/commands/suggestions")
async def command_suggestions(q: str | None = None):
    ALL = [
        {"cmd": "ollama ps",              "description": "List currently running models"},
        {"cmd": "ollama list",            "description": "List all installed models"},
        {"cmd": "ollama version",         "description": "Show Ollama version"},
        {"cmd": "ollama run llama3.2",    "description": "Run llama3.2 interactively"},
        {"cmd": "ollama run mistral",     "description": "Run Mistral 7B"},
        {"cmd": "ollama pull llama3.2",   "description": "Pull latest Llama 3.2"},
        {"cmd": "ollama pull mistral",    "description": "Pull Mistral 7B"},
        {"cmd": "ollama pull phi4",       "description": "Pull Microsoft Phi-4"},
        {"cmd": "ollama pull gemma3:4b",  "description": "Pull Google Gemma 3 4B"},
        {"cmd": "ollama show llama3.2",   "description": "Show model info for llama3.2"},
        {"cmd": "ollama rm llama3.2",     "description": "Remove llama3.2"},
    ]
    if q:
        ql = q.lower()
        return {"items": [s for s in ALL if ql in s["cmd"] or ql in s["description"]]}
    return {"items": ALL}


@router.websocket("/commands/stream")
async def command_stream(ws: WebSocket):
    # Auth removed — accept all connections
    await ws.accept()
    await ws.send_json({"event_type": "connected", "message": "Terminal ready. Type an Ollama command."})

    anon_user = get_anonymous_user()
    request_id = uuid4().hex

    try:
        while True:
            incoming = await ws.receive_json()
            action = incoming.get("action", "run")

            if action == "stop":
                rid = incoming.get("request_id", request_id)
                await process_supervisor.stop(rid)
                await ws.send_json({"event_type": "stopped", "request_id": rid})
                continue

            if action == "ping":
                await ws.send_json({"event_type": "pong"})
                continue

            command = incoming.get("command", "").strip()
            if not validate_command(command):
                await ws.send_json({
                    "event_type": "error", "request_id": request_id,
                    "payload": {"message": f"Command not allowed: '{command}'. Only Ollama commands are permitted."},
                })
                continue

            process = await asyncio.create_subprocess_exec(
                *command.split(" "),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await session_registry.register(ActiveSession(request_id=request_id, process=process))
            await ws.send_json({"event_type": "started", "request_id": request_id, "payload": {"command": command}})
            started = datetime.now(timezone.utc)

            async with SessionLocal() as write_session:
                cmd_row = CommandHistory(
                    user_id=anon_user.id,
                    command=command,
                    command_type=command.split(" ")[1] if len(command.split(" ")) > 1 else "unknown",
                    status="started",
                    started_at=started,
                )
                write_session.add(cmd_row)
                write_session.add(StreamingSession(request_id=request_id, type="command", status="started"))
                await write_session.commit()

            output_buffer: list[str] = []
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text_line = line.decode("utf-8", errors="ignore")
                output_buffer.append(text_line)
                await ws.send_json({"event_type": "output", "request_id": request_id, "payload": {"line": text_line}})

            exit_code = await process.wait()
            await ws.send_json({"event_type": "done", "request_id": request_id, "payload": {"exit_code": exit_code}})

            completed = datetime.now(timezone.utc)
            duration_ms = int((completed - started).total_seconds() * 1000)

            async with SessionLocal() as write_session:
                result2 = await write_session.execute(
                    select(CommandHistory).where(CommandHistory.command == command, CommandHistory.started_at == started)
                )
                cmd_saved = result2.scalar_one_or_none()
                if cmd_saved:
                    cmd_saved.status = "done" if exit_code == 0 else "error"
                    cmd_saved.output = "".join(output_buffer)[-12000:]
                    cmd_saved.completed_at = completed
                    cmd_saved.duration_ms = duration_ms
                stream_q = await write_session.execute(select(StreamingSession).where(StreamingSession.request_id == request_id))
                stream_row = stream_q.scalar_one_or_none()
                if stream_row:
                    stream_row.status = "done"
                    stream_row.ended_at = completed
                await write_session.commit()

            await session_registry.pop(request_id)
            request_id = uuid4().hex

    except WebSocketDisconnect:
        return
