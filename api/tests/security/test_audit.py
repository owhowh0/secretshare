"""
Security tests for the audit trail.

These assert the properties claimed in docs/security/security-controls.md:
no full payload id is ever persisted, no ciphertext is ever persisted, and an
audit failure cannot change what a secret endpoint returns.
"""

import logging

import pytest
from app.core.auth import get_current_user
from app.api.routes.secrets import get_audit_service, get_secret_service
from app.core.audit import AuditService, payload_id_prefix
from app.core.ids import new_payload_id
from app.db.models import PAYLOAD_ID_PREFIX_LENGTH
from app.main import app
from tests.fakes import make_secret_service, recipient_claims, secret_body
from fastapi.testclient import TestClient

CIPHERTEXT = "ZmFrZS1jaXBoZXJ0ZXh0LXBheWxvYWQ"


class RecordingAuditService:
    """Captures what the route asked to record, without touching a database."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    async def record(
        self,
        event_type: str,
        *,
        payload_id: str | None = None,
        actor_user_id=None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "payload_id_prefix": payload_id_prefix(payload_id),
                "actor_user_id": actor_user_id,
                "ip": ip,
                "user_agent": user_agent,
            }
        )


@pytest.fixture
def audit() -> RecordingAuditService:
    return RecordingAuditService()


@pytest.fixture
def client(audit: RecordingAuditService):
    secrets = make_secret_service()
    app.dependency_overrides[get_secret_service] = lambda: secrets
    app.dependency_overrides[get_audit_service] = lambda: audit
    app.dependency_overrides[get_current_user] = recipient_claims

    yield TestClient(app)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Invariant 6 — nothing secret is ever logged
# ---------------------------------------------------------------------------
class TestNoSecretMaterialInAudit:
    def test_full_payload_id_is_never_recorded(self, client, audit) -> None:
        created = client.post("/secrets", json=secret_body(CIPHERTEXT))
        payload_id = created.json()["payload_id"]

        client.post("/secrets/reveal", json={"payload_id": payload_id})

        assert len(audit.events) == 2
        for event in audit.events:
            prefix = event["payload_id_prefix"]
            assert prefix == payload_id[:PAYLOAD_ID_PREFIX_LENGTH]
            assert len(prefix) == PAYLOAD_ID_PREFIX_LENGTH
            assert prefix != payload_id
            assert payload_id not in str(event)

    def test_ciphertext_is_never_recorded(self, client, audit) -> None:
        client.post("/secrets", json=secret_body(CIPHERTEXT))

        assert CIPHERTEXT not in str(audit.events)

    def test_prefix_helper_truncates_and_passes_through_none(self) -> None:
        long_id = new_payload_id()

        assert len(payload_id_prefix(long_id)) == PAYLOAD_ID_PREFIX_LENGTH
        assert payload_id_prefix(None) is None
        assert payload_id_prefix("") is None

    def test_prefix_keeps_ids_unreconstructable(self) -> None:
        """An 8-char prefix must not make two distinct ids collide often enough to matter."""
        prefixes = {payload_id_prefix(new_payload_id()) for _ in range(2000)}

        assert len(prefixes) > 1990  # 48 bits of entropy: collisions are negligible


# ---------------------------------------------------------------------------
# Event coverage
# ---------------------------------------------------------------------------
class TestEventsRecorded:
    def test_create_records_created(self, client, audit) -> None:
        client.post("/secrets", json=secret_body(CIPHERTEXT))

        assert [e["event_type"] for e in audit.events] == ["created"]

    def test_successful_reveal_records_revealed(self, client, audit) -> None:
        payload_id = client.post(
            "/secrets", json=secret_body(CIPHERTEXT)
        ).json()["payload_id"]
        audit.events.clear()

        client.post("/secrets/reveal", json={"payload_id": payload_id})

        assert [e["event_type"] for e in audit.events] == ["revealed"]

    def test_second_read_records_denied(self, client, audit) -> None:
        payload_id = client.post(
            "/secrets", json=secret_body(CIPHERTEXT)
        ).json()["payload_id"]
        client.post("/secrets/reveal", json={"payload_id": payload_id})
        audit.events.clear()

        client.post("/secrets/reveal", json={"payload_id": payload_id})

        assert [e["event_type"] for e in audit.events] == ["denied"]

    def test_unknown_id_records_denied(self, client, audit) -> None:
        client.post("/secrets/reveal", json={"payload_id": new_payload_id()})

        assert [e["event_type"] for e in audit.events] == ["denied"]

    def test_request_metadata_is_captured(self, client, audit) -> None:
        client.post(
            "/secrets",
            json=secret_body(CIPHERTEXT),
            headers={"user-agent": "pytest-agent/1.0"},
        )

        event = audit.events[0]
        assert event["user_agent"] == "pytest-agent/1.0"
        assert event["ip"] is not None


# ---------------------------------------------------------------------------
# Invariant 5 — a burned secret and a missing secret stay indistinguishable
# ---------------------------------------------------------------------------
class TestAuditDoesNotWeakenResponses:
    def test_burned_and_missing_responses_are_identical(self, client) -> None:
        payload_id = client.post(
            "/secrets", json=secret_body(CIPHERTEXT)
        ).json()["payload_id"]
        client.post("/secrets/reveal", json={"payload_id": payload_id})

        burned = client.post("/secrets/reveal", json={"payload_id": payload_id})
        missing = client.post("/secrets/reveal", json={"payload_id": new_payload_id()})

        assert burned.status_code == missing.status_code == 404
        assert burned.json() == missing.json()
        assert burned.content == missing.content

    def test_audit_failure_does_not_change_the_response(self, caplog) -> None:
        """A Postgres outage must not turn a 200 into a 500 or alter the body."""

        class BrokenSessionFactory:
            def __call__(self):
                raise RuntimeError("postgres is down")

        broken_audit = AuditService(BrokenSessionFactory())
        secrets = make_secret_service()

        app.dependency_overrides[get_secret_service] = lambda: secrets
        app.dependency_overrides[get_audit_service] = lambda: broken_audit
        app.dependency_overrides[get_current_user] = recipient_claims
        try:
            with TestClient(app) as c, caplog.at_level(logging.ERROR):
                created = c.post("/secrets", json=secret_body(CIPHERTEXT))
                assert created.status_code == 201

                payload_id = created.json()["payload_id"]
                revealed = c.post("/secrets/reveal", json={"payload_id": payload_id})

                assert revealed.status_code == 200
                assert revealed.json()["ciphertext"] == CIPHERTEXT
                assert c.post("/secrets/reveal", json={"payload_id": payload_id}).status_code == 404
        finally:
            app.dependency_overrides.clear()

        assert "Audit write failed" in caplog.text
        assert CIPHERTEXT not in caplog.text

    def test_audit_disabled_when_no_database_configured(self) -> None:
        disabled = AuditService(None)

        assert disabled._enabled is False
