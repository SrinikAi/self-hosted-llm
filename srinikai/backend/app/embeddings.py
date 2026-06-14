"""Embeddings provider.

Tries an OpenAI-compatible embeddings endpoint (e.g. a llama-server started
with --embeddings, or any embeddings service set via EMBEDDINGS_URL). If that
is unavailable, falls back to a deterministic local hashing embedder so the RAG
pipeline always works (lower semantic quality — swap in a real embedder for prod).
"""
from __future__ import annotations

import hashlib
import math

import httpx

from .config import settings
from .models import EMBED_DIM


def _normalize(v: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def _local_embed(text: str) -> list[float]:
    """Deterministic bag-of-hashed-tokens embedding (offline fallback)."""
    vec = [0.0] * EMBED_DIM
    for tok in text.lower().split():
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % EMBED_DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    return _normalize(vec)


def embed(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        return [0.0] * EMBED_DIM

    url = settings.embeddings_url
    if url:
        try:
            resp = httpx.post(
                f"{url}/v1/embeddings",
                json={"model": settings.embeddings_model, "input": text},
                timeout=settings.request_timeout_seconds,
            )
            if resp.status_code == 200:
                data = resp.json()["data"][0]["embedding"]
                if len(data) == EMBED_DIM:
                    return _normalize([float(x) for x in data])
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            pass  # fall through to local

    return _local_embed(text)


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # vectors are pre-normalized
