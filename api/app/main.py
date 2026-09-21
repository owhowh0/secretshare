import logging
import ssl
from contextlib import asynccontextmanager

from app.api.errors import register_exception_handlers
from app.api.routes.keys import router as keys_router
from app.api.routes.secrets import router as secrets_router
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.headers import SecurityHeadersMiddleware
from app.core.limits import BODY_OVERHEAD_BYTES, BodySizeLimitMiddleware
from app.core.proxy import TrustedProxyMiddleware
from app.core.logging_filters import install_secret_path_redaction
from app.db.session import create_engine, create_session_factory, dispose_engine
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from starlette.responses import JSONResponse

logger = logging.getLogger("secretshare.api")

# Installed at import time so no request can be logged before it is in place.
install_secret_path_redaction()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Re-installed here because uvicorn applies its own logging config after
    # this module is imported, which replaces the handlers on uvicorn.access.
    install_secret_path_redaction()

    settings = get_settings()

    redis_kwargs: dict = {"decode_responses": True}
    if settings.tls_ca_cert and settings.redis_url.startswith("rediss://"):
        redis_kwargs["ssl_ca_certs"] = settings.tls_ca_cert
        redis_kwargs["ssl_cert_reqs"] = "required"
        redis_kwargs["ssl_check_hostname"] = False
    redis = Redis.from_url(settings.redis_url, **redis_kwargs)
    app.state.redis = redis

    engine = (
        create_engine(settings.database_url, tls_ca_cert=settings.tls_ca_cert)
        if settings.database_url
        else None
    )
    app.state.db_engine = engine
    app.state.db_session_factory = create_session_factory(engine) if engine else None

    if engine is None:
        logger.warning("DATABASE_URL is not set — audit logging is disabled.")

    try:
        yield
    finally:
        await redis.aclose()
        app.state.redis = None
        if engine is not None:
            await dispose_engine(engine)
        app.state.db_engine = None
        app.state.db_session_factory = None


app = FastAPI(
    title="SecretShare API",
    version="0.1.0",
    root_path=settings.root_path,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware runs in reverse registration order, so the body size limit is
# added last to make it the outermost layer: an oversized request is rejected
# before any other middleware or route buffers it.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    BodySizeLimitMiddleware,
    max_body_bytes=settings.max_payload_bytes + BODY_OVERHEAD_BYTES,
)
# Outermost of all: every layer (rate limiter, audit, CORS) must see the real
# client address, not the proxy's.
app.add_middleware(TrustedProxyMiddleware, trusted_proxies=settings.trusted_proxies)

# Include routers
app.include_router(secrets_router)
app.include_router(keys_router)
register_exception_handlers(app)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to SecretShare API"}


@app.get("/me", tags=["Auth"])
async def me(claims: dict = Depends(get_current_user)):
    """
    Returns the decoded Keycloak token claims for the current user.
    Use this to verify OAuth is wired up correctly.
    """
    return claims


# Global exception handler
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        f"Unhandled error processing {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
