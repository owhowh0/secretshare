# Ephemeral ciphertext storage in Redis. Every key carries a TTL, so a secret
# that is never read still disappears on its own.
from redis.asyncio import Redis


class SecretStore:
    def __init__(self, redis: Redis):
        self._redis = redis

    # store envelope payload in redis with automated expiration TTL
    async def put(self, payload_id: str, payload: str, *, ttl_seconds: int) -> None:
        await self._redis.set(f"s:{payload_id}", payload, ex=ttl_seconds)

    # Non-destructive check for bot previews and existence verification
    async def exists(self, payload_id: str) -> bool:
        return bool(await self._redis.exists(f"s:{payload_id}"))

    # retrieves data and instantly destroys
    async def burn(self, payload_id: str) -> str | None:
        return await self._redis.getdel(f"s:{payload_id}")
