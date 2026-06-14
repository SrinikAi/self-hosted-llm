"""Long-term user memory: store and semantically retrieve facts.

Storage:
- Postgres: native pgvector column + `<=>` (cosine distance) ordering, indexable.
- SQLite (dev): JSON-encoded vectors + in-Python cosine ranking.

Used by the chat flow to (a) persist salient user statements as memories and
(b) retrieve the most relevant ones to inject into the system prompt (RAG).
"""
from __future__ import annotations

import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import settings
from .embeddings import cosine, embed
from .models import Memory

_IS_PG = settings.database_url.startswith("postgresql")


def add_memory(db: Session, user_id: str, content: str, kind: str = "fact") -> None:
    content = (content or "").strip()
    if len(content) < 8:
        return
    vec = embed(content)
    stored = vec if _IS_PG else json.dumps(vec)
    db.add(Memory(user_id=user_id, content=content, kind=kind, embedding=stored))
    db.commit()


def retrieve(db: Session, user_id: str, query: str, k: int | None = None) -> list[str]:
    k = k or settings.memory_top_k
    qvec = embed(query)

    if _IS_PG:
        # pgvector cosine distance; smaller = closer. Convert to similarity.
        rows = db.execute(
            text(
                "SELECT content, 1 - (embedding <=> :q) AS score "
                "FROM memories WHERE user_id = :uid AND embedding IS NOT NULL "
                "ORDER BY embedding <=> :q LIMIT :k"
            ),
            {"q": str(qvec), "uid": user_id, "k": k},
        ).all()
        return [r.content for r in rows if r.score is not None and r.score >= settings.memory_min_score]

    # SQLite fallback: brute-force cosine in Python.
    rows = db.scalars(
        select(Memory).where(Memory.user_id == user_id, Memory.embedding.is_not(None))
    ).all()
    scored = []
    for m in rows:
        try:
            v = json.loads(m.embedding)
        except (TypeError, json.JSONDecodeError):
            continue
        scored.append((cosine(qvec, v), m.content))
    scored.sort(reverse=True)
    return [c for s, c in scored[:k] if s >= settings.memory_min_score]


def format_context(snippets: list[str]) -> str | None:
    if not snippets:
        return None
    return "\n".join(f"- {s}" for s in snippets)
