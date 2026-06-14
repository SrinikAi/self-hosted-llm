"""SriniKai API — FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import settings
from .database import init_db
from .limiter import limiter
from .middleware import SecurityHeadersMiddleware
from .routers import auth, chat

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("srinikai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.jwt_secret in ("dev-insecure-secret-change-me", "CHANGE_ME_TO_A_LONG_RANDOM_STRING"):
        if settings.is_prod:
            raise RuntimeError("Refusing to start in production with the default JWT_SECRET.")
        log.warning("Using an insecure default JWT_SECRET — set JWT_SECRET in .env for anything real.")
    log.info("SriniKai API ready (env=%s)", settings.env)
    yield


app = FastAPI(title="SriniKai API", version="0.1.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS — restricted to configured origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(chat.router)


@app.exception_handler(Exception)
async def unhandled_exc(request: Request, exc: Exception):
    # Never leak internals to clients.
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "service": settings.app_name}
