import os
from contextlib import asynccontextmanager

from app.api.routes.secrets import router as secrets_router
from app.core.auth import get_current_user
from fastapi import Depends, FastAPI
from redis.asyncio import Redis

root_path = f"/pr-{os.environ['PR_NUMBER']}" if os.getenv("PR_NUMBER") else ""


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
