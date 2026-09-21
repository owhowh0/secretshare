"""Secret endpoints: configurable TTL, payload size limits, domain exceptions.

The real SecretService runs over an in-memory store (tests/fakes.py), so the
TTL defaulting, bound checks and exception mapping are the production code.
"""

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from app.api.errors import SECRET_NOT_FOUND_DETAIL, SECRET_STORE_UNAVAILABLE_DETAIL
from app.api.routes.secrets import (
    create_rate_limit,
    get_audit_service,
    get_secret_service,
    retrieve_rate_limit,
)
from app.core.auth import get_current_user
from app.core.config import Settings
from app.main import app
from app.schemas.secrets import (
    MAX_CIPHERTEXT_BYTES,
    MAX_TTL_SECONDS,
    MIN_TTL_SECONDS,
    EncryptedKeyItem,
)
from app.services.exceptions import (
    InvalidSecretTTLError,
    SecretAccessDeniedError,
    SecretNotFoundError,
    SecretStoreUnavailableError,
)
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from tests.fakes import InMemorySecretStore, make_secret_service

RECIPIENT_ID = "alice"
OTHER_USER_ID = "bob"
DEVICE_ID = UUID("00000000-0000-0000-0000-000000000001")
ENCRYPTED_KEYS = [
    {
        "device_id": str(DEVICE_ID),
        "platform": "web",
        "encrypted_aes_key": "ZW5jcnlwdGVkLWtleQ==",
    }
]
ENCRYPTED_KEY_ITEMS = [
    EncryptedKeyItem(
        device_id=DEVICE_ID,
        platform="web",
        encrypted_aes_key="ZW5jcnlwdGVkLWtleQ==",
    )
]
IV = "MTIzNDU2Nzg5MDEy"
CIPHERTEXT = "this-is-a-fake-ciphertext"
DEFAULT_TTL = Settings(_env_file=None).secret_ttl_seconds


class RecordingAuditService:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def record(self, event_type: str, **kwargs) -> None:
        self.events.append(event_type)


class BrokenStore:
    """A store whose Redis is down."""

    async def put(self, payload_id: str, payload: str, *, ttl_seconds: int) -> None:
        raise RedisConnectionError("connection refused")

    async def exists(self, payload_id: str) -> bool:
        raise RedisConnectionError("connection refused")

    async def burn(self, payload_id: str) -> str | None:
        raise RedisConnectionError("connection refused")


@pytest.fixture
def store() -> InMemorySecretStore:
    return InMemorySecretStore()


@pytest.fixture
def audit() -> RecordingAuditService:
    return RecordingAuditService()


def _install(service, audit, current_user: dict | None = None) -> TestClient:
    app.dependency_overrides[get_secret_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit
    app.dependency_overrides[create_rate_limit] = lambda: None
    app.dependency_overrides[retrieve_rate_limit] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: (
        current_user
        if current_user is not None
        else {"preferred_username": RECIPIENT_ID, "sub": "auth-sub-alice"}
    )
    return TestClient(app)


@pytest.fixture
def client(store, audit):
    yield _install(make_secret_service(store), audit)
    app.dependency_overrides.clear()


@pytest.fixture
def broken_client(audit):
    yield _install(make_secret_service(BrokenStore()), audit)
    app.dependency_overrides.clear()


def _create(client: TestClient, **custom_fields):
    payload = {
        "recipient_id": RECIPIENT_ID,
        "encrypted_keys": ENCRYPTED_KEYS,
        "iv": IV,
        "ciphertext": CIPHERTEXT,
        **custom_fields,
    }
    return client.post("/secrets", json=payload)


# ---------------------------------------------------------------------------
# Basic lifecycle & Exists endpoint
# ---------------------------------------------------------------------------


def test_create_secret(client: TestClient) -> None:
    response = _create(client)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"payload_id", "ttl_seconds", "expires_at"}
    assert len(body["payload_id"]) >= 43


def test_check_secret_exists(client: TestClient) -> None:
    payload_id = _create(client).json()["payload_id"]

    res_exists = client.get(f"/secrets/{payload_id}/exists")
    assert res_exists.status_code == 200
    assert res_exists.json() == {"exists": True}

    res_missing = client.get("/secrets/unknown-id/exists")
    assert res_missing.status_code == 200
    assert res_missing.json() == {"exists": False}


def test_retrieve_secret_burns_envelope(client: TestClient) -> None:
    payload_id = _create(client).json()["payload_id"]

    first_response = client.post("/secrets/reveal", json={"payload_id": payload_id})
    assert first_response.status_code == 200
    data = first_response.json()
    assert data["recipient_id"] == RECIPIENT_ID
    assert data["ciphertext"] == CIPHERTEXT
    assert data["iv"] == IV
    assert len(data["encrypted_keys"]) == 1

    second_response = client.post("/secrets/reveal", json={"payload_id": payload_id})
    assert second_response.status_code == 404
    assert second_response.json() == {"detail": "Secret not found or already retrieved"}


def test_retrieve_secret_unauthorized_recipient(store, audit) -> None:
    client = _install(
        make_secret_service(store),
        audit,
        current_user={"preferred_username": OTHER_USER_ID, "sub": "sub-bob"},
    )
    try:
        payload_id = _create(client).json()["payload_id"]
        response = client.post("/secrets/reveal", json={"payload_id": payload_id})
        assert response.status_code == 403
        assert response.json() == {
            "detail": "You are not the intended recipient of this secret."
        }
    finally:
        app.dependency_overrides.clear()


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
        assert (
            before + timedelta(seconds=3600)
            <= expires_at
            <= after + timedelta(seconds=3600)
        )

    @pytest.mark.parametrize(
        "ttl", [0, -1, MIN_TTL_SECONDS - 1, MAX_TTL_SECONDS + 1, 10**9]
    )
    def test_ttl_out_of_bounds_is_rejected(self, client, store, ttl):
        response = _create(client, ttl_seconds=ttl)
        assert response.status_code == 422
        assert store.payloads == {}


# ---------------------------------------------------------------------------
# Payload size limits
# ---------------------------------------------------------------------------


class TestPayloadSize:
    def test_payload_at_limit_is_accepted(self, client):
        response = _create(client, ciphertext="A" * MAX_CIPHERTEXT_BYTES)
        assert response.status_code == 201

    def test_payload_over_limit_is_rejected(self, client, store):
        response = _create(client, ciphertext="A" * (MAX_CIPHERTEXT_BYTES + 1))
        assert response.status_code in (413, 422)
        assert store.payloads == {}

    def test_empty_payload_is_rejected(self, client):
        assert _create(client, ciphertext="").status_code == 422


# ---------------------------------------------------------------------------
# Domain exceptions -> HTTP
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


# ---------------------------------------------------------------------------
# Service layer, without HTTP
# ---------------------------------------------------------------------------


class TestSecretService:
    async def test_retrieve_missing_raises_not_found(self):
        with pytest.raises(SecretNotFoundError):
            await make_secret_service().retrieve_secret(
                "missing", caller_identity=RECIPIENT_ID
            )

    async def test_create_then_retrieve(self):
        service = make_secret_service()
        created = await service.create_secret(
            recipient_id=RECIPIENT_ID,
            encrypted_keys=ENCRYPTED_KEY_ITEMS,
            iv=IV,
            ciphertext=CIPHERTEXT,
            ttl_seconds=900,
        )

        assert created.ttl_seconds == 900
        envelope = await service.retrieve_secret(
            created.payload_id, caller_identity=RECIPIENT_ID
        )
        assert envelope.ciphertext == CIPHERTEXT
        assert envelope.recipient_id == RECIPIENT_ID
        assert envelope.iv == IV

        with pytest.raises(SecretNotFoundError):
            await service.retrieve_secret(
                created.payload_id, caller_identity=RECIPIENT_ID
            )

    async def test_retrieve_wrong_recipient_raises_access_denied(self):
        service = make_secret_service()
        created = await service.create_secret(
            recipient_id=RECIPIENT_ID,
            encrypted_keys=ENCRYPTED_KEY_ITEMS,
            iv=IV,
            ciphertext=CIPHERTEXT,
        )

        with pytest.raises(SecretAccessDeniedError):
            await service.retrieve_secret(
                created.payload_id, caller_identity=OTHER_USER_ID
            )
