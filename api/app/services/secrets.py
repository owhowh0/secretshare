import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.ids import new_payload_id
from app.schemas.secrets import EncryptedKeyItem
from app.services.exceptions import (
    InvalidSecretTTLError,
    SecretAccessDeniedError,
    SecretNotFoundError,
    SecretStoreUnavailableError,
)
from app.storage.redis_store import BurnStatus, SecretStore
from redis.exceptions import RedisError


@dataclass(frozen=True)
class CreatedSecret:
    payload_id: str
    ttl_seconds: int
    expires_at: datetime


@dataclass(frozen=True)
class SecretEnvelope:
    recipient_id: str
    encrypted_keys: list[EncryptedKeyItem]
    iv: str
    ciphertext: str


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

    async def check_exists(self, payload_id: str) -> bool:
        try:
            return await self._store.exists(payload_id)
        except RedisError as exc:
            raise SecretStoreUnavailableError() from exc

    async def create_secret(
        self,
        recipient_id: str,
        encrypted_keys: list[EncryptedKeyItem],
        iv: str,
        ciphertext: str,
        ttl_seconds: int | None = None,
    ) -> CreatedSecret:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        if not self._min_ttl <= ttl <= self._max_ttl:
            raise InvalidSecretTTLError(ttl, self._min_ttl, self._max_ttl)

        payload_id = new_payload_id()
        envelope_data = {
            "recipient_id": recipient_id,
            "encrypted_keys": [
                k.model_dump(mode="json") if hasattr(k, "model_dump") else k
                for k in encrypted_keys
            ],
            "iv": iv,
            "ciphertext": ciphertext,
        }

        try:
            await self._store.put(
                payload_id, json.dumps(envelope_data), ttl_seconds=ttl
            )
        except RedisError as exc:
            raise SecretStoreUnavailableError() from exc

        return CreatedSecret(
            payload_id=payload_id,
            ttl_seconds=ttl,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
        )

    async def retrieve_secret(
        self, payload_id: str, caller_identity: str
    ) -> SecretEnvelope:
        # The recipient check happens inside the store's atomic burn: a denied
        # caller must leave the secret intact for its real recipient.
        try:
            result = await self._store.burn_for_recipient(payload_id, caller_identity)
        except RedisError as exc:
            raise SecretStoreUnavailableError() from exc

        if result.status is BurnStatus.MISSING:
            raise SecretNotFoundError()
        if result.status is BurnStatus.DENIED:
            raise SecretAccessDeniedError()

        data = json.loads(result.payload)

        return SecretEnvelope(
            recipient_id=data["recipient_id"],
            encrypted_keys=[
                EncryptedKeyItem(**item) for item in data["encrypted_keys"]
            ],
            iv=data["iv"],
            ciphertext=data["ciphertext"],
        )
