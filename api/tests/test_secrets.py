"""Secret endpoints: configurable TTL, payload size limits, domain exceptions.

The real SecretService runs over an in-memory store (tests/fakes.py), so the
TTL defaulting, bound checks and exception mapping are the production code.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from app.api.errors import SECRET_NOT_FOUND_DETAIL, SECRET_STORE_UNAVAILABLE_DETAIL
from app.api.routes.secrets import (
    create_rate_limit,
    get_audit_service,
    get_secret_service,
    retrieve_rate_limit,
)
from app.core.config import Settings
from app.main import app
from app.schemas.secrets import MAX_CIPHERTEXT_BYTES, MAX_TTL_SECONDS, MIN_TTL_SECONDS
from app.services.exceptions import (
    InvalidSecretTTLError,
    SecretNotFoundError,
    SecretStoreUnavailableError,
)
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from tests.fakes import InMemorySecretStore, make_secret_service

CIPHERTEXT = "this-is-a-fake-ciphertext"
DEFAULT_TTL = Settings(_env_file=None).secret_ttl_seconds


class RecordingAuditService:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def record(self, event_type: str, **kwargs) -> None:
        self.events.append(event_type)


class BrokenStore:
    """A store whose Redis is down."""

    async def put(self, payload_id: str, ciphertext: str, *, ttl_seconds: int) -> None:
        raise RedisConnectionError("connection refused")

    async def burn(self, payload_id: str) -> str | None:
        raise RedisConnectionError("connection refused")


@pytest.fixture
def store() -> InMemorySecretStore:
    return InMemorySecretStore()


@pytest.fixture
def audit() -> RecordingAuditService:
    return RecordingAuditService()


def _install(service, audit) -> TestClient:
    app.dependency_overrides[get_secret_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit
    # Limits are covered in test_config.py; keep them out of the way here.
    app.dependency_overrides[create_rate_limit] = lambda: None
    app.dependency_overrides[retrieve_rate_limit] = lambda: None
    return TestClient(app)


@pytest.fixture
def client(store, audit):
    yield _install(make_secret_service(store), audit)
    app.dependency_overrides.clear()


@pytest.fixture
def broken_client(audit):
    yield _install(make_secret_service(BrokenStore()), audit)
    app.dependency_overrides.clear()


def _create(client: TestClient, **body):
    return client.post("/secrets", json={"ciphertext": CIPHERTEXT, **body})


# ---------------------------------------------------------------------------
# Basic lifecycle
# ---------------------------------------------------------------------------


def test_create_secret(client: TestClient) -> None:
    response = _create(client)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"payload_id", "ttl_seconds", "expires_at"}
    assert len(body["payload_id"]) >= 43


def test_retrieve_secret_burns_payload(client: TestClient) -> None:
    payload_id = _create(client).json()["payload_id"]

    first_response = client.post("/secrets/reveal", json={"payload_id": payload_id})

    assert first_response.status_code == 200
    assert first_response.json() == {"ciphertext": CIPHERTEXT}

    second_response = client.post("/secrets/reveal", json={"payload_id": payload_id})

    assert second_response.status_code == 404
    assert second_response.json() == {"detail": "Secret not found or already retrieved"}


# ---------------------------------------------------------------------------
# Configurable TTL
# ---------------------------------------------------------------------------


class TestTtl:
    def test_default_ttl_when_omitted(self, client, store):
        body = _create(client).json()

        assert body["ttl_seconds"] == DEFAULT_TTL
        assert store.ttls[body["payload_id"]] == DEFAULT_TTL

    def test_explicit_null_uses_default(self, client, store):
        body = _create(client, ttl_seconds=None).json()

        assert body["ttl_seconds"] == DEFAULT_TTL

    @pytest.mark.parametrize("ttl", [MIN_TTL_SECONDS, 3600, MAX_TTL_SECONDS])
    def test_custom_ttl_within_bounds_is_stored(self, client, store, ttl):
        response = _create(client, ttl_seconds=ttl)

        assert response.status_code == 201
        body = response.json()
        assert body["ttl_seconds"] == ttl
        assert store.ttls[body["payload_id"]] == ttl

    def test_expires_at_matches_ttl(self, client):
        before = datetime.now(timezone.utc)
        body = _create(client, ttl_seconds=3600).json()
        after = datetime.now(timezone.utc)

        expires_at = datetime.fromisoformat(body["expires_at"])

        assert expires_at.tzinfo is not None
        assert before + timedelta(seconds=3600) <= expires_at <= after + timedelta(seconds=3600)

    @pytest.mark.parametrize(
        "ttl", [0, -1, MIN_TTL_SECONDS - 1, MAX_TTL_SECONDS + 1, 10**9]
    )
    def test_ttl_out_of_bounds_is_rejected(self, client, store, ttl):
        response = _create(client, ttl_seconds=ttl)

        assert response.status_code == 422
        assert store.payloads == {}, "an out-of-bounds secret was stored"

    @pytest.mark.parametrize("ttl", ["ten minutes", 600.5, [600]])
    def test_non_integer_ttl_is_rejected(self, client, store, ttl):
        response = _create(client, ttl_seconds=ttl)

        assert response.status_code == 422
        assert store.payloads == {}

    def test_ttl_bounds_are_published_in_openapi(self, client):
        schema = client.get("/openapi.json").json()
        ttl = schema["components"]["schemas"]["SecretCreateRequest"]["properties"]["ttl_seconds"]
        integer = next(option for option in ttl["anyOf"] if option.get("type") == "integer")

        assert integer["minimum"] == MIN_TTL_SECONDS
        assert integer["maximum"] == MAX_TTL_SECONDS


# ---------------------------------------------------------------------------
# Payload size limits
# ---------------------------------------------------------------------------


class TestPayloadSize:
    def test_payload_at_limit_is_accepted(self, client):
        response = client.post("/secrets", json={"ciphertext": "A" * MAX_CIPHERTEXT_BYTES})

        assert response.status_code == 201

    def test_payload_over_limit_is_rejected(self, client, store):
        response = client.post(
            "/secrets", json={"ciphertext": "A" * (MAX_CIPHERTEXT_BYTES + 1)}
        )

        assert response.status_code in (413, 422)
        assert store.payloads == {}

    def test_multibyte_payload_is_measured_in_bytes(self, client, store):
        # Under the character cap and small enough to clear the body-size
        # middleware, but 2 bytes per character in UTF-8 puts it over the byte
        # cap, so only the schema's byte check can catch it.
        text = "é" * (MAX_CIPHERTEXT_BYTES // 2 + 200)
        assert len(text) <= MAX_CIPHERTEXT_BYTES < len(text.encode("utf-8"))
        body = json.dumps({"ciphertext": text}, ensure_ascii=False).encode("utf-8")

        response = client.post(
            "/secrets", content=body, headers={"content-type": "application/json"}
        )

        assert response.status_code == 422
        assert "bytes" in response.text
        assert store.payloads == {}

    def test_empty_payload_is_rejected(self, client):
        assert client.post("/secrets", json={"ciphertext": ""}).status_code == 422


# ---------------------------------------------------------------------------
# Domain exceptions → HTTP
# ---------------------------------------------------------------------------


class TestDomainExceptionHandlers:
    def test_unknown_id_maps_to_404(self, client, audit):
        response = client.post("/secrets/reveal", json={"payload_id": "never-existed"})

        assert response.status_code == 404
        assert response.json() == {"detail": SECRET_NOT_FOUND_DETAIL}
        assert audit.events == ["denied"]

    def test_burned_and_unknown_are_indistinguishable(self, client):
        payload_id = _create(client).json()["payload_id"]
        client.post("/secrets/reveal", json={"payload_id": payload_id})

        burned = client.post("/secrets/reveal", json={"payload_id": payload_id})
        unknown = client.post("/secrets/reveal", json={"payload_id": "never-existed"})

        assert burned.status_code == unknown.status_code == 404
        assert burned.content == unknown.content

    def test_audit_trail_for_success_and_denial(self, client, audit):
        payload_id = _create(client).json()["payload_id"]
        client.post("/secrets/reveal", json={"payload_id": payload_id})
        client.post("/secrets/reveal", json={"payload_id": payload_id})

        assert audit.events == ["created", "revealed", "denied"]

    def test_store_outage_on_create_maps_to_503(self, broken_client, audit):
        response = _create(broken_client)

        assert response.status_code == 503
        assert response.json() == {"detail": SECRET_STORE_UNAVAILABLE_DETAIL}
        assert response.headers["retry-after"] == "5"
        assert audit.events == []

    def test_store_outage_on_reveal_maps_to_503(self, broken_client):
        response = broken_client.post("/secrets/reveal", json={"payload_id": "any"})

        assert response.status_code == 503
        assert "connection refused" not in response.text

    def test_error_responses_keep_security_headers(self, client):
        response = client.post("/secrets/reveal", json={"payload_id": "never-existed"})

        assert "no-store" in response.headers["cache-control"]
        assert response.headers["x-content-type-options"] == "nosniff"


# ---------------------------------------------------------------------------
# Service layer, without HTTP
# ---------------------------------------------------------------------------


class TestSecretService:
    async def test_retrieve_missing_raises_not_found(self):
        with pytest.raises(SecretNotFoundError):
            await make_secret_service().retrieve_secret("missing")

    async def test_create_then_retrieve(self):
        service = make_secret_service()

        created = await service.create_secret(CIPHERTEXT, ttl_seconds=900)

        assert created.ttl_seconds == 900
        assert await service.retrieve_secret(created.payload_id) == CIPHERTEXT
        with pytest.raises(SecretNotFoundError):
            await service.retrieve_secret(created.payload_id)

    @pytest.mark.parametrize("ttl", [MIN_TTL_SECONDS - 1, MAX_TTL_SECONDS + 1])
    async def test_service_enforces_bounds_without_the_schema(self, ttl):
        store = InMemorySecretStore()
        service = make_secret_service(store)

        with pytest.raises(InvalidSecretTTLError) as exc_info:
            await service.create_secret(CIPHERTEXT, ttl_seconds=ttl)

        assert exc_info.value.ttl_seconds == ttl
        assert store.payloads == {}

    async def test_service_uses_configured_bounds(self):
        settings = Settings(
            _env_file=None,
            secret_ttl_min_seconds=60,
            secret_ttl_seconds=120,
            secret_ttl_max_seconds=180,
        )
        service = make_secret_service(settings=settings)

        assert (await service.create_secret(CIPHERTEXT)).ttl_seconds == 120
        assert (await service.create_secret(CIPHERTEXT, ttl_seconds=60)).ttl_seconds == 60
        with pytest.raises(InvalidSecretTTLError):
            await service.create_secret(CIPHERTEXT, ttl_seconds=181)

    async def test_redis_errors_become_domain_errors(self):
        service = make_secret_service(BrokenStore())

        with pytest.raises(SecretStoreUnavailableError):
            await service.create_secret(CIPHERTEXT)
        with pytest.raises(SecretStoreUnavailableError):
            await service.retrieve_secret("any")


class TestInvalidTtlHandler:
    def test_live_bounds_narrower_than_schema_map_to_422(self, audit, store):
        # The schema bounds are fixed at import; if the service is configured
        # tighter, the domain error is what rejects the request.
        settings = Settings(
            _env_file=None,
            secret_ttl_min_seconds=300,
            secret_ttl_seconds=600,
            secret_ttl_max_seconds=900,
        )
        client = _install(make_secret_service(store, settings), audit)
        try:
            response = _create(client, ttl_seconds=3600)
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 422
        assert response.json() == {"detail": "ttl_seconds must be between 300 and 900"}
        assert store.payloads == {}
        assert audit.events == []
