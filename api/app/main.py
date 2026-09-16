import logging
import os
from contextlib import asynccontextmanager

from app.api.routes.secrets import router as secrets_router
from app.core.auth import get_current_user
from app.core.config import get_settings
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from starlette.responses import JSONResponse

logger = logging.getLogger("secretshare.api")

default_root = f"/pr-{os.environ['PR_NUMBER']}/api" if os.getenv("PR_NUMBER") else "/api"
root_path = os.getenv("API_ROOT_PATH", default_root)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )
    app.state.redis = redis
    try:
        yield
    finally:
        await redis.aclose()


app = FastAPI(
    title="SecretShare API",
    version="0.1.0",
    root_path=root_path,
    lifespan=lifespan,
)

# CORS
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(secrets_router)


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
