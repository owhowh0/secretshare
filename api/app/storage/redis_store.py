# class that will in async way store the data in the payload for the 600 seconds, 
from redis.asyncio import Redis

class SecretStore:
    def __init__(self, redis: Redis, ttl_seconds: int = 600):
        self._redis = redis
        self._ttl = ttl_seconds

# store in redis with automated timer
    async def put(self, payload_id: str, ciphertext: str) -> None:
        await self._redis.set(f"s:{payload_id}", ciphertext, ex=self._ttl)

# retrieves data and instantly destroys
    async def burn(self, payload_id: str) -> str | None:
        return await self._redis.getdel(f"s:{payload_id}")