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
        # API returns JSON/SSE only; lock down what a response may load.
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if settings.is_prod:
            resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return resp
