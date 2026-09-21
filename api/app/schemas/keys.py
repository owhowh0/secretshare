import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

PEM_PATTERN = re.compile(
    r"^-----BEGIN PUBLIC KEY-----\s+[A-Za-z0-9+/=\s]+\s+-----END PUBLIC KEY-----$"
)


class KeyRegisterRequest(BaseModel):
    public_key: str = Field(
        ...,
        description="Exported SPKI Public Key PEM string (RSA-OAEP 2048-bit.",
    )
    platform: str = Field(
        default="web",
        description="Origin platform partition ('web', 'slack', 'teams', 'keycloak').",
    )
    label: str | None = Field(
        default=None,
        max_length=64,
        description="Optional human-readable device identifier/label.",
    )

    @field_validator("public_key")
    @classmethod
    def validate_pem(cls, value: str) -> str:
        clean = value.strip()
        if not PEM_PATTERN.match(clean):
            raise ValueError("Invalid SPKI Public Key PEM format.")
        if len(clean) > 4096:
            raise ValueError("Public key PEM too large.")
        return clean

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        allowed = {"web", "slack", "teams", "keycloak"}
        if value.lower() not in allowed:
            raise ValueError(f"Platform must be one of {allowed}")
        return value.lower()


class DeviceKeyItem(BaseModel):
    device_id: UUID
    platform: str
    public_key: str
    label: str | None
    created_at: datetime


class UserPublicKeysResponse(BaseModel):
    user_id: str
    keys: list[DeviceKeyItem]
