import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

AUDIT_EVENT_TYPES = ("created", "revealed", "expired", "denied")

PAYLOAD_ID_PREFIX_LENGTH = 8


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    platform_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    device_keys: Mapped[list["DeviceKey"]] = relationship(back_populates="user")

    __table_args__ = (
        UniqueConstraint("platform", "platform_user_id", name="uq_users_platform_user"),
        CheckConstraint("platform IN ('slack', 'teams')", name="ck_users_platform"),
    )


class DeviceKey(Base):
    """Public keys only. A private key must never reach the server."""

    __tablename__ = "device_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="device_keys")

    __table_args__ = (Index("ix_device_keys_user_id", "user_id"),)


class AuditEvent(Base):
    """
    Append-only record of security-relevant events.

    Security property: holds no secret material. `payload_id_prefix` is capped at
    8 characters by a database CHECK constraint, so a full 43-character payload id
    cannot be persisted even if a caller passes one — the write fails instead of
    silently storing a usable id.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_id_prefix: Mapped[str | None] = mapped_column(
        String(PAYLOAD_ID_PREFIX_LENGTH), nullable=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created', 'revealed', 'expired', 'denied')",
            name="ck_audit_events_event_type",
        ),
        CheckConstraint(
            f"payload_id_prefix IS NULL OR length(payload_id_prefix) <= {PAYLOAD_ID_PREFIX_LENGTH}",
            name="ck_audit_events_prefix_length",
        ),
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_payload_id_prefix", "payload_id_prefix"),
    )
