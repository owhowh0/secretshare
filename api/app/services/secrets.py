from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.exceptions import RedisError

from app.core.ids import new_payload_id
from app.services.exceptions import (
    InvalidSecretTTLError,
    SecretNotFoundError,
    SecretStoreUnavailableError,
)
from app.storage.redis_store import SecretStore


@dataclass(frozen=True)
class CreatedSecret:
    payload_id: str
    ttl_seconds: int
    expires_at: datetime


class SecretService:
    def __init__(
        self,
        store: SecretStore,
        *,
        default_ttl_seconds: int,
        min_ttl_seconds: int,
        max_ttl_seconds: int,
    ) -> None:
        self._store = store
        self._default_ttl = default_ttl_seconds
        self._min_ttl = min_ttl_seconds
        self._max_ttl = max_ttl_seconds

    async def create_secret(
        self, ciphertext: str, ttl_seconds: int | None = None
    ) -> CreatedSecret:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        # The request schema checks the same bounds, but the service is the
        # authority: any caller that skips the schema still cannot store a
        # secret that outlives the configured maximum.
        if not self._min_ttl <= ttl <= self._max_ttl:
            raise InvalidSecretTTLError(ttl, self._min_ttl, self._max_ttl)

        payload_id = new_payload_id()
        try:
            await self._store.put(payload_id, ciphertext, ttl_seconds=ttl)
        except RedisError as exc:
            raise SecretStoreUnavailableError() from exc

        return CreatedSecret(
            payload_id=payload_id,
            ttl_seconds=ttl,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
        )

    async def retrieve_secret(self, payload_id: str) -> str:
        try:
            ciphertext = await self._store.burn(payload_id)
        except RedisError as exc:
            raise SecretStoreUnavailableError() from exc

        if ciphertext is None:
            raise SecretNotFoundError()
        return ciphertext
