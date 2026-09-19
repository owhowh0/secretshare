# Ephemeral ciphertext storage in Redis. Every key carries a TTL, so a secret
# that is never read still disappears on its own.
from redis.asyncio import Redis


class SecretStore:
    def __init__(self, redis: Redis):
        self._redis = redis

    # store in redis with automated timer
    async def put(self, payload_id: str, ciphertext: str, *, ttl_seconds: int) -> None:
        await self._redis.set(f"s:{payload_id}", ciphertext, ex=ttl_seconds)

    # retrieves data and instantly destroys
    async def burn(self, payload_id: str) -> str | None:
        return await self._redis.getdel(f"s:{payload_id}")
