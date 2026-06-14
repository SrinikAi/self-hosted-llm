"""Internet access tool: keyless web search + page fetch with sanitization.

Search uses DuckDuckGo's HTML endpoint (no API key). Fetch downloads a page and
strips it down to readable text. Both are defensive: timeouts, size caps, and
SSRF guards against private/loopback addresses.
"""
from __future__ import annotations

import html
import ipaddress
import re
import socket
from urllib.parse import urlparse, quote_plus, unquote

import httpx

from .config import settings

_UA = "Mozilla/5.0 (compatible; SriniKai/1.0)"
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"\s+")
_DDG_RESULT_RE = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_DDG_SNIPPET_RE = re.compile(r'class="result__snippet"[^>]*>(?P<snippet>.*?)</a>', re.DOTALL | re.IGNORECASE)


def _clean(s: str) -> str:
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub("", s))).strip()


def _is_public_url(url: str) -> bool:
    """Block non-http(s) and private/loopback/link-local targets (SSRF guard)."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        infos = socket.getaddrinfo(p.hostname, None)
        for *_, sockaddr in infos:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except (socket.gaierror, ValueError):
        return False


def search(query: str, max_results: int | None = None) -> list[dict]:
    max_results = max_results or settings.web_max_results
    try:
        resp = httpx.get(
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
            headers={"User-Agent": _UA},
            timeout=15,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return []
        body = resp.text
    except httpx.HTTPError:
        return []

    results, snippets = [], _DDG_SNIPPET_RE.findall(body)
    for i, m in enumerate(_DDG_RESULT_RE.finditer(body)):
        if len(results) >= max_results:
            break
        raw = m.group("url")
        # DDG wraps targets in a redirect: /l/?uddg=<encoded>
        mu = re.search(r"uddg=([^&]+)", raw)
        url = unquote(mu.group(1)) if mu else raw
        if not url.startswith("http"):
            continue
        results.append({
            "title": _clean(m.group("title")),
            "url": url,
            "snippet": _clean(snippets[i]) if i < len(snippets) else "",
        })
    return results


def fetch(url: str, max_chars: int | None = None) -> str:
    max_chars = max_chars or settings.web_fetch_chars
    if not _is_public_url(url):
        return ""
    try:
        resp = httpx.get(url, headers={"User-Agent": _UA}, timeout=15, follow_redirects=True)
        if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", "text/html"):
            return ""
        text = _SCRIPT_RE.sub(" ", resp.text)
        return _clean(text)[:max_chars]
    except httpx.HTTPError:
        return ""


def research(query: str) -> str | None:
    """Search + fetch top hit, return a context block for the model."""
    hits = search(query)
    if not hits:
        return None
    lines = ["Web search results:"]
    for h in hits:
        lines.append(f"- {h['title']} ({h['url']})\n  {h['snippet']}")
    page = fetch(hits[0]["url"])
    if page:
        lines.append(f"\nExcerpt from {hits[0]['url']}:\n{page}")
    return "\n".join(lines)
