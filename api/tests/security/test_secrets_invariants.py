"""
The security tests required by CLAUDE.md §11.8.

These assert the invariants from §2 directly rather than through a fake store:
the burn tests talk to a real Redis, because atomicity is a property of
GETDEL, not of the service wrapper around it.

The Redis-backed tests are skipped unless TEST_REDIS_URL is set, so the
default `pytest` run stays offline. Run them with:

    TEST_REDIS_URL=redis://127.0.0.1:6379/0 pytest
"""

import asyncio
import os

import pytest
import pytest_asyncio
from app.api.routes.secrets import get_audit_service, get_secret_service
from app.core.config import Settings, get_settings
from app.core.ids import new_payload_id
from app.main import app
from app.services.secrets import SecretService
from app.storage.redis_store import SecretStore
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

REDIS_URL = os.getenv("TEST_REDIS_URL")

requires_redis = pytest.mark.skipif(
    not REDIS_URL, reason="TEST_REDIS_URL is not set"
)

CIPHERTEXT = "ZmFrZS1jaXBoZXJ0ZXh0LXBheWxvYWQ"
TTL_SECONDS = 600


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
    return SecretService(SecretStore(redis, ttl_seconds=TTL_SECONDS))


@pytest_asyncio.fixture
async def client(redis):
    """Client wired to a real Redis, with only the audit sink stubbed out."""
    app.state.redis = redis
    app.dependency_overrides[get_audit_service] = lambda: NullAuditService()
    app.dependency_overrides[get_settings] = lambda: Settings()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class TestAtomicBurn:
    """Invariant 3: two concurrent readers must never both receive the secret."""

    @requires_redis
    async def test_burn_is_single_delivery(self, service):
        for _ in range(5):
            payload_id = await service.create_secret(CIPHERTEXT)

            results = await asyncio.gather(
                *[service.retrieve_secret(payload_id) for _ in range(20)]
            )

            winners = [r for r in results if r is not None]
            assert len(winners) == 1, f"{len(winners)} readers received the secret"
            assert winners[0] == CIPHERTEXT
            assert results.count(None) == 19

    @requires_redis
    async def test_second_read_is_a_miss(self, service):
        payload_id = await service.create_secret(CIPHERTEXT)

        assert await service.retrieve_secret(payload_id) == CIPHERTEXT
        assert await service.retrieve_secret(payload_id) is None


class TestNoEnumerationOracle:
    """Invariant 5: a missing secret and a burned secret are indistinguishable."""

    @requires_redis
    async def test_missing_and_burned_are_identical(self, client):
        created = await client.post("/secrets", json={"ciphertext": CIPHERTEXT})
        payload_id = created.json()["payload_id"]
        assert (await client.post("/secrets/reveal", json={"payload_id": payload_id})).status_code == 200

        burned = await client.post("/secrets/reveal", json={"payload_id": payload_id})
        never_existed = await client.post("/secrets/reveal", json={"payload_id": new_payload_id()})

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
    """CLAUDE.md §7: text only, max 64 KB."""

    @requires_redis
    async def test_oversized_payload_rejected(self, client, redis):
        settings = Settings()
        oversized = "A" * (settings.max_payload_bytes + 1)

        before = len(await redis.keys("s:*"))
        response = await client.post("/secrets", json={"ciphertext": oversized})
        after = len(await redis.keys("s:*"))

        assert response.status_code in (413, 422)
        assert after == before, "an oversized payload was written to Redis"

    @requires_redis
    async def test_payload_at_the_limit_is_accepted(self, client):
        settings = Settings()
        at_limit = "A" * settings.max_payload_bytes

        response = await client.post("/secrets", json={"ciphertext": at_limit})

        assert response.status_code == 201


class TestTtl:
    """Ciphertext must expire on its own even if it is never read."""

    @requires_redis
    async def test_ttl_is_set(self, client, redis):
        created = await client.post("/secrets", json={"ciphertext": CIPHERTEXT})
        payload_id = created.json()["payload_id"]

        ttl = await redis.ttl(f"s:{payload_id}")

        assert 0 < ttl <= TTL_SECONDS
        assert ttl > TTL_SECONDS - 60, "TTL is far below the configured window"


class TestSecurityHeaders:
    """CLAUDE.md §11.6 plus the headers a JSON-only API should always send."""

    @requires_redis
    async def test_reveal_response_is_not_cacheable(self, client):
        created = await client.post("/secrets", json={"ciphertext": CIPHERTEXT})
        payload_id = created.json()["payload_id"]

        response = await client.post("/secrets/reveal", json={"payload_id": payload_id})

        assert "no-store" in response.headers["cache-control"]
        assert response.headers["referrer-policy"] == "no-referrer"

    @requires_redis
    async def test_headers_present_on_a_miss_too(self, client):
        response = await client.post("/secrets/reveal", json={"payload_id": new_payload_id()})

        assert response.status_code == 404
        assert "no-store" in response.headers["cache-control"]
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
