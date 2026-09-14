import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.routes.secrets import router as secrets_router

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
