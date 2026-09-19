"""
End-to-end audit tests: a real HTTP request must produce a real audit row.

The other audit suites either stub AuditService (test_audit.py) or call it
directly (test_audit_db.py), so neither notices when the wiring in
app/main.py or get_audit_service() stops handing the route a live session
factory. These tests exercise the route with the real AuditService.

Skipped unless TEST_DATABASE_URL is set, so the default `pytest` run stays
offline. Run them with:

    TEST_DATABASE_URL=postgresql+asyncpg://user:pass@127.0.0.1:5432/secretshare pytest
"""

import os

import pytest
import pytest_asyncio
from app.api.routes.secrets import get_secret_service
from app.core.config import Settings, get_settings
from app.db.models import PAYLOAD_ID_PREFIX_LENGTH, AuditEvent
from app.db.session import create_engine, create_session_factory, dispose_engine
from app.main import app
from tests.fakes import make_secret_service
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TEST_DATABASE_URL is not set"
)

CIPHERTEXT = "ZmFrZS1jaXBoZXJ0ZXh0LXBheWxvYWQ"


@pytest_asyncio.fixture
async def session_factory():
    engine = create_engine(DATABASE_URL)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await dispose_engine(engine)


async def _fetch(session_factory, prefix: str) -> list[AuditEvent]:
    async with session_factory() as session:
        result = await session.execute(
            select(AuditEvent).where(AuditEvent.payload_id_prefix == prefix)
        )
        return list(result.scalars())


def _client_with(session_factory, *, audit_enabled: bool = True):
    """
    Builds a client whose app state carries a real session factory, the way
    the lifespan handler does when DATABASE_URL is set.
    """
    secrets = make_secret_service()
    app.state.db_session_factory = session_factory
    app.dependency_overrides[get_secret_service] = lambda: secrets
    app.dependency_overrides[get_settings] = lambda: Settings(
        audit_enabled=audit_enabled
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def client(session_factory):
    async with _client_with(session_factory) as ac:
        yield ac
    app.dependency_overrides.clear()
    app.state.db_session_factory = None


class TestAuditReachesTheDatabase:
    async def test_create_writes_a_created_row(self, client, session_factory):
        response = await client.post(
            "/secrets",
            json={"ciphertext": CIPHERTEXT},
            headers={"user-agent": "route-probe/1.0"},
        )
        assert response.status_code == 201
        payload_id = response.json()["payload_id"]

        rows = await _fetch(session_factory, payload_id[:PAYLOAD_ID_PREFIX_LENGTH])
        assert len(rows) == 1
        assert rows[0].event_type == "created"
        assert rows[0].user_agent == "route-probe/1.0"
        assert rows[0].payload_id_prefix != payload_id

    async def test_reveal_then_burn_writes_revealed_then_denied(
        self, client, session_factory
    ):
        created = await client.post("/secrets", json={"ciphertext": CIPHERTEXT})
        payload_id = created.json()["payload_id"]
        prefix = payload_id[:PAYLOAD_ID_PREFIX_LENGTH]

        assert (await client.post("/secrets/reveal", json={"payload_id": payload_id})).status_code == 200
        assert (await client.post("/secrets/reveal", json={"payload_id": payload_id})).status_code == 404

        rows = await _fetch(session_factory, prefix)
        assert [row.event_type for row in rows] == ["created", "revealed", "denied"]

    async def test_full_payload_id_never_reaches_the_table(
        self, client, session_factory
    ):
        created = await client.post("/secrets", json={"ciphertext": CIPHERTEXT})
        payload_id = created.json()["payload_id"]

        rows = await _fetch(session_factory, payload_id[:PAYLOAD_ID_PREFIX_LENGTH])
        assert len(rows[0].payload_id_prefix) == PAYLOAD_ID_PREFIX_LENGTH
        assert payload_id not in (rows[0].payload_id_prefix or "")


class TestAuditEnabledSetting:
    async def test_disabled_setting_writes_nothing(self, session_factory):
        async with _client_with(session_factory, audit_enabled=False) as ac:
            created = await ac.post("/secrets", json={"ciphertext": CIPHERTEXT})
            payload_id = created.json()["payload_id"]
            assert (await ac.post("/secrets/reveal", json={"payload_id": payload_id})).status_code == 200

        app.dependency_overrides.clear()
        app.state.db_session_factory = None

        rows = await _fetch(session_factory, payload_id[:PAYLOAD_ID_PREFIX_LENGTH])
        assert rows == []

    async def test_secret_endpoints_still_work_without_a_database(self):
        """Invariant 5: an audit outage must not change what the route returns."""
        secrets = make_secret_service()
        app.state.db_session_factory = None
        app.dependency_overrides[get_secret_service] = lambda: secrets
        app.dependency_overrides[get_settings] = lambda: Settings(audit_enabled=True)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            created = await ac.post("/secrets", json={"ciphertext": CIPHERTEXT})
            assert created.status_code == 201
            payload_id = created.json()["payload_id"]

            revealed = await ac.post("/secrets/reveal", json={"payload_id": payload_id})
            assert revealed.status_code == 200
            assert revealed.json()["ciphertext"] == CIPHERTEXT
            assert (await ac.post("/secrets/reveal", json={"payload_id": payload_id})).status_code == 404

        app.dependency_overrides.clear()
