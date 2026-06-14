"""Authenticated chat: persists turns and streams the model reply via SSE.

Each request is scoped to the authenticated user. We never expose the raw
llama-server to clients; this proxy injects the hardened system prompt, trims
history, strips model identity from upstream, and stores the conversation.
"""
import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..deps import get_current_user
from ..limiter import limiter
from ..models import Conversation, Message, User
from ..prompts import build_messages
from ..schemas import ChatRequest, ConversationOut, MessageOut
from .. import memory as memory_svc
from .. import web as web_svc

router = APIRouter(prefix="/api", tags=["chat"])


def _load_history(db: Session, conversation_id: str) -> list[dict]:
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(settings.max_history_messages)
    ).all()
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows]


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    ).all()


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.get(Conversation, conversation_id)
    if convo is None or convo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return convo.messages


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.get(Conversation, conversation_id)
    if convo is None or convo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.delete(convo)
    db.commit()


@router.post("/chat")
@limiter.limit(settings.rate_limit_chat)
def chat(
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Resolve / create the conversation (ownership enforced).
    if body.conversation_id:
        convo = db.get(Conversation, body.conversation_id)
        if convo is None or convo.user_id != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        convo = Conversation(user_id=user.id, title=body.message[:60])
        db.add(convo)
        db.commit()
        db.refresh(convo)

    history = _load_history(db, convo.id)

    # Persist the user's turn now.
    db.add(Message(conversation_id=convo.id, role="user", content=body.message))
    db.commit()

    # ---- Context assembly: long-term memory (RAG) + optional web access ----
    context_blocks: list[str] = []
    mem = memory_svc.format_context(memory_svc.retrieve(db, user.id, body.message))
    if mem:
        context_blocks.append("What you remember about this user:\n" + mem)
    if body.web and settings.web_enabled:
        web_ctx = web_svc.research(body.message)
        if web_ctx:
            context_blocks.append(web_ctx)
    retrieved_context = "\n\n".join(context_blocks) if context_blocks else None

    # Persist this user message as a long-term memory for future recall.
    memory_svc.add_memory(db, user.id, body.message, kind="fact")

    messages = build_messages(history, body.message, retrieved_context)
    convo_id = convo.id
    user_id = user.id

    upstream_payload = {
        "model": settings.model_name,
        "messages": messages,
        "temperature": body.temperature,
        "stream": True,
    }

    def event_stream():
        acc: list[str] = []
        # First event carries the conversation id so the client can track it.
        yield f"data: {json.dumps({'conversation_id': convo_id})}\n\n"
        try:
            with httpx.stream(
                "POST",
                f"{settings.llama_server_url}/v1/chat/completions",
                json=upstream_payload,
                timeout=settings.request_timeout_seconds,
            ) as resp:
                if resp.status_code != 200:
                    yield f"data: {json.dumps({'error': 'model backend error'})}\n\n"
                    return
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content")
                    except (KeyError, IndexError, json.JSONDecodeError):
                        continue
                    if delta:
                        acc.append(delta)
                        # Re-emit only the content delta; never forward upstream model ids.
                        yield f"data: {json.dumps({'delta': delta})}\n\n"
        except httpx.HTTPError:
            yield f"data: {json.dumps({'error': 'model backend unavailable'})}\n\n"
        finally:
            # Persist assistant turn in a fresh session (generator outlives request db).
            full = "".join(acc).strip()
            if full:
                with SessionLocal() as s:
                    s.add(Message(conversation_id=convo_id, role="assistant", content=full))
                    c = s.get(Conversation, convo_id)
                    if c:
                        c.updated_at = c.updated_at  # touch via onupdate
                    s.commit()
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
