"""
Audit tests that run against a real PostgreSQL instance.

Skipped unless TEST_DATABASE_URL is set, so the default `pytest` run stays
offline. Run them with:

    TEST_DATABASE_URL=postgresql+asyncpg://user:pass@127.0.0.1:5432/secretshare pytest
"""

import os

import pytest
import pytest_asyncio
from app.core.audit import AuditService
from app.core.ids import new_payload_id
from app.db.models import PAYLOAD_ID_PREFIX_LENGTH, AuditEvent
from app.db.session import create_engine, create_session_factory, dispose_engine
from sqlalchemy import select, text

DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TEST_DATABASE_URL is not set"
)


@pytest_asyncio.fixture
async def session_factory():
    engine = create_engine(DATABASE_URL)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await dispose_engine(engine)


@pytest_asyncio.fixture
async def audit(session_factory):
    return AuditService(session_factory)


async def _fetch(session_factory, prefix: str) -> list[AuditEvent]:
    async with session_factory() as session:
        result = await session.execute(
            select(AuditEvent).where(AuditEvent.payload_id_prefix == prefix)
        )
        return list(result.scalars())


class TestAuditPersistence:
    async def test_record_persists_only_the_prefix(self, audit, session_factory):
        payload_id = new_payload_id()

        await audit.record(
            "created", payload_id=payload_id, ip="203.0.113.5", user_agent="ua/1.0"
        )

        rows = await _fetch(session_factory, payload_id[:PAYLOAD_ID_PREFIX_LENGTH])
        assert len(rows) == 1
        row = rows[0]
        assert row.event_type == "created"
        assert row.payload_id_prefix == payload_id[:PAYLOAD_ID_PREFIX_LENGTH]
        assert row.payload_id_prefix != payload_id
        assert str(row.ip) == "203.0.113.5"
        assert row.user_agent == "ua/1.0"
        assert row.created_at is not None

    async def test_long_user_agent_is_truncated(self, audit, session_factory):
        payload_id = new_payload_id()

        await audit.record("created", payload_id=payload_id, user_agent="A" * 5000)

        rows = await _fetch(session_factory, payload_id[:PAYLOAD_ID_PREFIX_LENGTH])
        assert len(rows[0].user_agent) == 256


class TestDatabaseLevelGuards:
    async def test_full_payload_id_is_rejected_by_the_database(self, session_factory):
        """Even a caller that bypasses AuditService cannot store a usable id."""
        payload_id = new_payload_id()

        with pytest.raises(Exception):
            async with session_factory() as session:
                await session.execute(
                    text(
                        "INSERT INTO audit_events (event_type, payload_id_prefix) "
                        "VALUES ('created', :pid)"
                    ),
                    {"pid": payload_id},
                )
                await session.commit()

    async def test_unknown_event_type_is_rejected(self, session_factory):
        with pytest.raises(Exception):
            async with session_factory() as session:
                await session.execute(
                    text("INSERT INTO audit_events (event_type) VALUES ('exfiltrated')")
                )
                await session.commit()

    async def test_audit_rows_cannot_be_updated(self, audit, session_factory):
        payload_id = new_payload_id()
        await audit.record("created", payload_id=payload_id)

        with pytest.raises(Exception):
            async with session_factory() as session:
                await session.execute(
                    text(
                        "UPDATE audit_events SET event_type = 'denied' "
                        "WHERE payload_id_prefix = :prefix"
                    ),
                    {"prefix": payload_id[:PAYLOAD_ID_PREFIX_LENGTH]},
                )
                await session.commit()

        rows = await _fetch(session_factory, payload_id[:PAYLOAD_ID_PREFIX_LENGTH])
        assert rows[0].event_type == "created"

    async def test_audit_rows_cannot_be_deleted(self, audit, session_factory):
        payload_id = new_payload_id()
        await audit.record("created", payload_id=payload_id)

        with pytest.raises(Exception):
            async with session_factory() as session:
                await session.execute(
                    text(
                        "DELETE FROM audit_events WHERE payload_id_prefix = :prefix"
                    ),
                    {"prefix": payload_id[:PAYLOAD_ID_PREFIX_LENGTH]},
                )
                await session.commit()

        rows = await _fetch(session_factory, payload_id[:PAYLOAD_ID_PREFIX_LENGTH])
        assert len(rows) == 1
