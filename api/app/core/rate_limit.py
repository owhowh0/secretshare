# rate limiter scoped per client ip and per limiter instance
import logging
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import Settings, get_settings

logger = logging.getLogger("secretshare.rate_limit")


class RateLimiter:
    """
    Fixed-window counter in Redis. The limit is read from Settings on every
    request (via `limit_of`), so it is configurable per environment and can be
    overridden in tests through the get_settings dependency.
    """

    def __init__(self, *, scope: str, limit_of: Callable[[Settings], int]):
        self._scope = scope
        self._limit_of = limit_of

    async def __call__(
        self,
        request: Request,
        settings: Settings = Depends(get_settings),
    ) -> None:
        redis: Redis | None = getattr(request.app.state, "redis", None)
        if redis is None:
            return

        limit = self._limit_of(settings)
        window = settings.rate_limit_window_seconds
        client_ip = request.client.host if request.client else "unknown"
        key = f"rl:{self._scope}:{client_ip}"

        try:
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, window)

            if current > limit:
                ttl = await redis.ttl(key)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests, slow down.",
                    headers={"Retry-After": str(max(ttl, 1))},
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Rate limiting skipped due to redis error: %s", exc)
            return
