from app.core.ids import new_payload_id
from app.storage.redis_store import SecretStore


class SecretService:
    def __init__(self, store: SecretStore) -> None:
        self._store = store

    async def create_secret(self, ciphertext: str) -> str:
        payload_id = new_payload_id()
        await self._store.put(payload_id, ciphertext)
        return payload_id

    async def retrieve_secret(self, payload_id: str) -> str | None:
        return await self._store.burn(payload_id)
