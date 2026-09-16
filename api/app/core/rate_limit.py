# rate limiter scoped per client ip and per limiter instance 
from redis.asyncio import Redis
from fastapi import HTTPException, Request, status


class RateLimiter:

    def __init__(self, *, limit: int, window_seconds: int, scope: str):
        self._limit = limit
        self._window = window_seconds
        self._scope = scope

    async def __call__(self, request: Request) -> None:
        redis: Redis = request.app.state.redis
        client_ip = request.client.host if request.client else "unknown"
        key = f"rl:{self._scope}:{client_ip}"

        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, self._window)

        if current > self._limit:
            ttl = await redis.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, slow down.",
                headers={"Retry-After": str(max(ttl, 1))},
            )
