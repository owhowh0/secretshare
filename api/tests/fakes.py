"""Shared test doubles.

Tests that do not need a real Redis run the real SecretService over this
in-memory store, so they exercise the same TTL checks and domain exceptions
the app uses instead of a hand-rolled copy of the service.
"""

import json

from app.core.config import Settings
from app.services.secrets import SecretService
from app.storage.redis_store import BurnResult, BurnStatus

# The identity every route test signs in as, and the recipient its secrets are
# addressed to, so a reveal by the default test user is authorised.
TEST_RECIPIENT = "testuser"
TEST_IV = "MTIzNDU2Nzg5MDEy"
TEST_ENCRYPTED_KEYS = [
    {
        "device_id": "00000000-0000-0000-0000-000000000001",
        "platform": "web",
        "encrypted_aes_key": "ZW5jcnlwdGVkLWtleQ==",
    }
]


def recipient_claims(username: str = TEST_RECIPIENT) -> dict:
    """Stand-in for get_current_user's decoded token claims."""
    return {"preferred_username": username, "sub": f"sub-{username}"}


def secret_body(
    ciphertext: str = "ZmFrZS1jaXBoZXJ0ZXh0",
    *,
    recipient_id: str = TEST_RECIPIENT,
    **extra,
) -> dict:
    """A valid POST /secrets body with the given ciphertext."""
    return {
        "recipient_id": recipient_id,
        "encrypted_keys": TEST_ENCRYPTED_KEYS,
        "iv": TEST_IV,
        "ciphertext": ciphertext,
        **extra,
    }


class InMemorySecretStore:
    def __init__(self) -> None:
        self.payloads: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def put(self, payload_id: str, ciphertext: str, *, ttl_seconds: int) -> None:
        self.payloads[payload_id] = ciphertext
        self.ttls[payload_id] = ttl_seconds

    async def exists(self, payload_id: str) -> bool:
        return payload_id in self.payloads

    async def burn_for_recipient(self, payload_id: str, recipient_id: str) -> BurnResult:
        # Mirrors the Lua script in SecretStore: only the recipient burns it.
        payload = self.payloads.get(payload_id)
        if payload is None:
            return BurnResult(BurnStatus.MISSING)
        try:
            envelope = json.loads(payload)
        except ValueError:
            return BurnResult(BurnStatus.DENIED)
        if not isinstance(envelope, dict) or envelope.get("recipient_id") != recipient_id:
            return BurnResult(BurnStatus.DENIED)
        self.ttls.pop(payload_id, None)
        return BurnResult(BurnStatus.BURNED, self.payloads.pop(payload_id))


def make_secret_service(
    store: InMemorySecretStore | None = None,
    settings: Settings | None = None,
) -> SecretService:
    settings = settings or Settings(_env_file=None)
    return SecretService(
        store if store is not None else InMemorySecretStore(),
        default_ttl_seconds=settings.secret_ttl_seconds,
        min_ttl_seconds=settings.secret_ttl_min_seconds,
        max_ttl_seconds=settings.secret_ttl_max_seconds,
    )
