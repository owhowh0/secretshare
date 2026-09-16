import logging
import uuid
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import PAYLOAD_ID_PREFIX_LENGTH, AuditEvent

logger = logging.getLogger("secretshare.audit")

AuditEventType = Literal["created", "revealed", "expired", "denied"]

MAX_USER_AGENT_LENGTH = 256


def payload_id_prefix(payload_id: str | None) -> str | None:
    """
    Upholds invariant 6: only the first 8 characters of a payload id may leave the
    request path. 8 base64url characters carry 48 bits, far short of the 256 bits
    needed to reconstruct the id, so an audit reader cannot recover a secret's URL.
    """
    if not payload_id:
        return None
    return payload_id[:PAYLOAD_ID_PREFIX_LENGTH]


class AuditService:
    """
    Writes append-only audit rows.

    Availability over audit completeness: a failed write is logged and swallowed so
    that a Postgres outage cannot change the status, body, or timing of a secret
    endpoint. That would otherwise break invariant 5 by making a burned id
    distinguishable from a missing one.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None,
        *,
        enabled: bool = True,
    ) -> None:
        self._session_factory = session_factory
        self._enabled = enabled and session_factory is not None

    async def record(
        self,
        event_type: AuditEventType,
        *,
        payload_id: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if not self._enabled:
            return

        assert self._session_factory is not None

        event = AuditEvent(
            event_type=event_type,
            payload_id_prefix=payload_id_prefix(payload_id),
            actor_user_id=actor_user_id,
            ip=ip,
            user_agent=user_agent[:MAX_USER_AGENT_LENGTH] if user_agent else None,
        )

        try:
            async with self._session_factory() as session:
                session.add(event)
                await session.commit()
        except Exception:
            logger.error(
                "Audit write failed for event_type=%s prefix=%s",
                event_type,
                event.payload_id_prefix,
                exc_info=True,
            )
