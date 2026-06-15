"""Security headers applied to every response."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # The backend also serves the static web UI, so the CSP must permit the
        # page's inline styles/scripts, the jsdelivr CDN libraries it loads, and
        # same-origin fetch/SSE to the API. Everything else stays denied.
        resp.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "base-uri 'none'; "
            "frame-ancestors 'none'"
        )
        if settings.is_prod:
            resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return resp
