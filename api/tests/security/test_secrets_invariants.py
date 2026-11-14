"""
Security tests for the invariants in context/06_secret_lifecycle_and_e2e_encryption.md §4.

These assert the invariants directly rather than through a fake store:
the burn tests talk to a real Redis, because atomicity is a property of
the Lua burn script, not of the service wrapper around it.

The Redis-backed tests are skipped unless TEST_REDIS_URL is set, so the
default `pytest` run stays offline. Run them with:

    TEST_REDIS_URL=redis://127.0.0.1:6379/0 pytest
"""

import asyncio
import os
from uuid import UUID

import pytest
import pytest_asyncio
from app.api.routes.secrets import (
    create_rate_limit,
    get_audit_service,
    get_secret_service,
    retrieve_rate_limit,
)
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.ids import new_payload_id
from app.main import app
from app.schemas.secrets import EncryptedKeyItem
from app.services.exceptions import SecretAccessDeniedError, SecretNotFoundError
from app.services.secrets import SecretService
from app.storage.redis_store import BurnStatus, SecretStore
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

REDIS_URL = os.getenv("TEST_REDIS_URL")

requires_redis = pytest.mark.skipif(not REDIS_URL, reason="TEST_REDIS_URL is not set")

CIPHERTEXT = "ZmFrZS1jaXBoZXJ0ZXh0LXBheWxvYWQ"
TTL_SECONDS = 600
RECIPIENT_ID = "alice"
OTHER_USER_ID = "bob"
DEVICE_ID = UUID("00000000-0000-0000-0000-000000000001")
ENCRYPTED_KEY_ITEMS = [
    EncryptedKeyItem(
        device_id=DEVICE_ID,
        platform="web",
        encrypted_aes_key="ZW5jcnlwdGVkLWtleQ==",
    )
]
ENCRYPTED_KEYS = [
    {
        "device_id": str(DEVICE_ID),
        "platform": "web",
        "encrypted_aes_key": "ZW5jcnlwdGVkLWtleQ==",
    }
]
IV = "MTIzNDU2Nzg5MDEy"


class NullAuditService:
    """Audit is covered by its own suites; keep these tests off the database."""

    async def record(self, event_type: str, **kwargs) -> None:
        return None


@pytest_asyncio.fixture
async def redis():
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def service(redis):
    return SecretService(
        SecretStore(redis),
        default_ttl_seconds=TTL_SECONDS,
        min_ttl_seconds=300,
        max_ttl_seconds=86400,
    )


@pytest_asyncio.fixture
async def client(redis):
    """Client wired to a real Redis, with only the audit sink stubbed out."""
    app.state.redis = redis
    app.dependency_overrides[get_audit_service] = lambda: NullAuditService()
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[create_rate_limit] = lambda: None
    app.dependency_overrides[retrieve_rate_limit] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {
        "preferred_username": RECIPIENT_ID,
        "sub": "auth-sub-alice",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    app.state.redis = None


def _make_payload(**custom_fields):
    return {
        "recipient_id": RECIPIENT_ID,
        "encrypted_keys": ENCRYPTED_KEYS,
        "iv": IV,
        "ciphertext": CIPHERTEXT,
        **custom_fields,
    }


class TestAtomicBurn:
    """Invariant 3: two concurrent readers must never both receive the secret."""

    @requires_redis
    async def test_burn_is_single_delivery(self, service):
        for _ in range(5):
            payload_id = (
                await service.create_secret(
                    recipient_id=RECIPIENT_ID,
                    encrypted_keys=ENCRYPTED_KEY_ITEMS,
                    iv=IV,
                    ciphertext=CIPHERTEXT,
                )
            ).payload_id

            results = await asyncio.gather(
                *[
                    service.retrieve_secret(payload_id, caller_identity=RECIPIENT_ID)
                    for _ in range(20)
                ],
                return_exceptions=True,
            )

            winners = [r for r in results if not isinstance(r, Exception)]
            misses = [r for r in results if isinstance(r, SecretNotFoundError)]
            assert len(winners) == 1, f"{len(winners)} readers received the secret"
            assert winners[0].ciphertext == CIPHERTEXT
            assert len(misses) == 19

    @requires_redis
    async def test_second_read_is_a_miss(self, service):
        payload_id = (
            await service.create_secret(
                recipient_id=RECIPIENT_ID,
                encrypted_keys=ENCRYPTED_KEY_ITEMS,
                iv=IV,
                ciphertext=CIPHERTEXT,
            )
        ).payload_id

        assert (
            await service.retrieve_secret(payload_id, caller_identity=RECIPIENT_ID)
        ).ciphertext == CIPHERTEXT
        with pytest.raises(SecretNotFoundError):
            await service.retrieve_secret(payload_id, caller_identity=RECIPIENT_ID)


class TestDeniedRevealIsNonDestructive:
    """
    A wrong recipient is refused without consuming the secret. The recipient
    check runs inside the same Redis script as the delete, so these assert the
    real Lua path, not a Python stand-in.
    """

    async def _create(self, service) -> str:
        return (
            await service.create_secret(
                recipient_id=RECIPIENT_ID,
                encrypted_keys=ENCRYPTED_KEY_ITEMS,
                iv=IV,
                ciphertext=CIPHERTEXT,
            )
        ).payload_id

    @requires_redis
    async def test_denied_reveal_leaves_key_and_ttl(self, service, redis):
        payload_id = await self._create(service)
        ttl_before = await redis.ttl(f"s:{payload_id}")

        with pytest.raises(SecretAccessDeniedError):
            await service.retrieve_secret(payload_id, caller_identity=OTHER_USER_ID)

        assert await redis.exists(f"s:{payload_id}") == 1
        assert 0 < await redis.ttl(f"s:{payload_id}") <= ttl_before

        envelope = await service.retrieve_secret(payload_id, caller_identity=RECIPIENT_ID)
        assert envelope.ciphertext == CIPHERTEXT
        assert await redis.exists(f"s:{payload_id}") == 0

    @requires_redis
    async def test_concurrent_intruders_cannot_starve_the_recipient(self, service):
        for _ in range(5):
            payload_id = await self._create(service)
            callers = [OTHER_USER_ID] * 10 + [RECIPIENT_ID] * 10

            results = await asyncio.gather(
                *[
                    service.retrieve_secret(payload_id, caller_identity=caller)
                    for caller in callers
                ],
                return_exceptions=True,
            )

            by_caller = list(zip(callers, results))
            winners = [r for _, r in by_caller if not isinstance(r, Exception)]
            assert len(winners) == 1, f"{len(winners)} readers received the secret"
            assert winners[0].recipient_id == RECIPIENT_ID
            # Every intruder is refused, whether before or after the burn it is
            # either a denial or a miss — never a delivery.
            for caller, result in by_caller:
                if caller == OTHER_USER_ID:
                    assert isinstance(result, (SecretAccessDeniedError, SecretNotFoundError))

    @requires_redis
    async def test_unparseable_payload_is_never_deleted(self, redis):
        store = SecretStore(redis)
        payload_id = new_payload_id()
        await redis.set(f"s:{payload_id}", "not json", ex=60)
        try:
            result = await store.burn_for_recipient(payload_id, RECIPIENT_ID)

            assert result.status is BurnStatus.DENIED
            assert result.payload is None
            assert await redis.exists(f"s:{payload_id}") == 1
        finally:
            await redis.delete(f"s:{payload_id}")

    @requires_redis
    async def test_missing_key_reports_missing(self, redis):
        result = await SecretStore(redis).burn_for_recipient(new_payload_id(), RECIPIENT_ID)

        assert result.status is BurnStatus.MISSING

    @requires_redis
    async def test_route_denies_then_serves_recipient(self, client):
        created = await client.post("/secrets", json=_make_payload())
        payload_id = created.json()["payload_id"]

        app.dependency_overrides[get_current_user] = lambda: {
            "preferred_username": OTHER_USER_ID,
            "sub": "auth-sub-bob",
        }
        denied = await client.post("/secrets/reveal", json={"payload_id": payload_id})

        app.dependency_overrides[get_current_user] = lambda: {
            "preferred_username": RECIPIENT_ID,
            "sub": "auth-sub-alice",
        }
        revealed = await client.post("/secrets/reveal", json={"payload_id": payload_id})
        burned = await client.post("/secrets/reveal", json={"payload_id": payload_id})

        assert denied.status_code == 403
        assert revealed.status_code == 200
        assert revealed.json()["ciphertext"] == CIPHERTEXT
        assert burned.status_code == 404


class TestNoEnumerationOracle:
    """Invariant 5: a missing secret and a burned secret are indistinguishable."""

    @requires_redis
    async def test_missing_and_burned_are_identical(self, client):
        created = await client.post("/secrets", json=_make_payload())
        payload_id = created.json()["payload_id"]
        assert (
            await client.post("/secrets/reveal", json={"payload_id": payload_id})
        ).status_code == 200

        burned = await client.post("/secrets/reveal", json={"payload_id": payload_id})
        never_existed = await client.post(
            "/secrets/reveal", json={"payload_id": new_payload_id()}
        )

        assert burned.status_code == never_existed.status_code == 404
        assert burned.content == never_existed.content

        # Date varies between the two requests and says nothing about the id.
        def comparable(response):
            return {
                key.lower(): value
                for key, value in response.headers.items()
                if key.lower() != "date"
            }

        assert comparable(burned) == comparable(never_existed)


class TestPayloadIds:
    """Invariant 4: ids come from secrets.token_urlsafe(32), nothing weaker."""

    def test_payload_id_entropy(self):
        ids = [new_payload_id() for _ in range(10_000)]

        assert len(set(ids)) == 10_000, "payload id collision"
        assert min(len(i) for i in ids) >= 43


class TestPayloadSizeLimit:
    """NFR-07: text only, max 64 KB."""

    @requires_redis
    async def test_oversized_payload_rejected(self, client, redis):
        settings = Settings()
        oversized = "A" * (settings.max_payload_bytes + 1)

        before = len(await redis.keys("s:*"))
        response = await client.post(
            "/secrets", json=_make_payload(ciphertext=oversized)
        )
        after = len(await redis.keys("s:*"))

        assert response.status_code in (413, 422)
        assert after == before, "an oversized payload was written to Redis"

    @requires_redis
    async def test_payload_at_the_limit_is_accepted(self, client):
        settings = Settings()
        at_limit = "A" * settings.max_payload_bytes

        response = await client.post(
            "/secrets", json=_make_payload(ciphertext=at_limit)
        )

        assert response.status_code == 201


class TestTtl:
    """Ciphertext must expire on its own even if it is never read."""

    @requires_redis
    async def test_ttl_is_set(self, client, redis):
        created = await client.post("/secrets", json=_make_payload())
        payload_id = created.json()["payload_id"]

        ttl = await redis.ttl(f"s:{payload_id}")

        assert 0 < ttl <= TTL_SECONDS
        assert ttl > TTL_SECONDS - 60, "TTL is far below the configured window"

    @requires_redis
    async def test_requested_ttl_reaches_redis(self, client, redis):
        created = await client.post("/secrets", json=_make_payload(ttl_seconds=3600))
        assert created.status_code == 201
        payload_id = created.json()["payload_id"]

        ttl = await redis.ttl(f"s:{payload_id}")

        assert 3600 - 60 < ttl <= 3600

    @requires_redis
    async def test_ttl_above_maximum_never_reaches_redis(self, client, redis):
        before = len(await redis.keys("s:*"))
        response = await client.post(
            "/secrets", json=_make_payload(ttl_seconds=86400 + 1)
        )
        after = len(await redis.keys("s:*"))

        assert response.status_code == 422
        assert after == before


class TestSecurityHeaders:
    """SR-28 (control API-5): the headers a JSON-only API should always send."""

    @requires_redis
    async def test_reveal_response_is_not_cacheable(self, client):
        created = await client.post("/secrets", json=_make_payload())
        payload_id = created.json()["payload_id"]

        response = await client.post("/secrets/reveal", json={"payload_id": payload_id})

        assert "no-store" in response.headers["cache-control"]
        assert response.headers["referrer-policy"] == "no-referrer"

    @requires_redis
    async def test_headers_present_on_a_miss_too(self, client):
        response = await client.post(
            "/secrets/reveal", json={"payload_id": new_payload_id()}
        )

        assert response.status_code == 404
        assert "no-store" in response.headers["cache-control"]
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
