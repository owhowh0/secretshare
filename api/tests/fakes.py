"""Shared test doubles.

Tests that do not need a real Redis run the real SecretService over this
in-memory store, so they exercise the same TTL checks and domain exceptions
the app uses instead of a hand-rolled copy of the service.
"""

from app.core.config import Settings
from app.services.secrets import SecretService


class InMemorySecretStore:
    def __init__(self) -> None:
        self.payloads: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def put(self, payload_id: str, ciphertext: str, *, ttl_seconds: int) -> None:
        self.payloads[payload_id] = ciphertext
        self.ttls[payload_id] = ttl_seconds

    async def burn(self, payload_id: str) -> str | None:
        self.ttls.pop(payload_id, None)
        return self.payloads.pop(payload_id, None)


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
