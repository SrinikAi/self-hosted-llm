"""SriniKai MCP server (stdio).

Exposes SriniKai's tools to any MCP client (Claude Desktop, IDEs, etc.):
  - web_search(query)        : keyless web search
  - fetch_url(url)           : fetch + clean a public web page
  - search_memory(email, q)  : semantic search over a user's stored memories

Run:  python -m app.mcp_server
Register in an MCP client with command `python` args `["-m","app.mcp_server"]`
and cwd = srinikai/backend (so .env / DB resolve).
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .database import SessionLocal
from .models import User
from . import web as web_svc
from . import memory as memory_svc

mcp = FastMCP("srinikai")


@mcp.tool()
def web_search(query: str, max_results: int = 4) -> list[dict]:
    """Search the web and return a list of {title, url, snippet}."""
    return web_svc.search(query, max_results=max_results)


@mcp.tool()
def fetch_url(url: str, max_chars: int = 4000) -> str:
    """Fetch a public web page and return cleaned, readable text."""
    return web_svc.fetch(url, max_chars=max_chars)


@mcp.tool()
def search_memory(email: str, query: str, k: int = 4) -> list[str]:
    """Semantic search over a user's long-term memories (by account email)."""
    from sqlalchemy import select

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower().strip()))
        if not user:
            return []
        return memory_svc.retrieve(db, user.id, query, k=k)


if __name__ == "__main__":
    mcp.run()
