from datetime import datetime
from uuid import UUID

from app.core.config import get_settings
from pydantic import BaseModel, Field, field_validator

# Resolved at import time so the limits appear in the OpenAPI schema. The
# server stays blind to the envelope's structure (invariant 1) — only the
# total size is judged, never the contents. The service layer re-checks the
# TTL bounds against the live settings.
_settings = get_settings()
MAX_CIPHERTEXT_BYTES = _settings.max_payload_bytes
MIN_TTL_SECONDS = _settings.secret_ttl_min_seconds
MAX_TTL_SECONDS = _settings.secret_ttl_max_seconds


class EncryptedKeyItem(BaseModel):
    device_id: UUID
    platform: str
    encrypted_aes_key: str = Field(
        description="Base64 encoded RSA-OAEP encrypted AES key."
    )


class SecretCreateRequest(BaseModel):
    recipient_id: str = Field(
        min_length=1, max_length=255, description="Platform user ID of the recipient."
    )
    encrypted_keys: list[EncryptedKeyItem] = Field(
        min_length=1, description="AES key encrypted for each active recipient device."
    )
    iv: str = Field(
        min_length=1,
        max_length=64,
        description="Base64 encoded 12-byte initialization vector.",
    )

    ciphertext: str = Field(
        min_length=1,
        max_length=MAX_CIPHERTEXT_BYTES,
        description=f"Opaque ciphertext, at most {MAX_CIPHERTEXT_BYTES} bytes UTF-8.",
    )
    ttl_seconds: int | None = Field(
        default=None,
        ge=MIN_TTL_SECONDS,
        le=MAX_TTL_SECONDS,
        description=(
            "Lifetime of the secret in seconds if it is never read, "
            f"{MIN_TTL_SECONDS}–{MAX_TTL_SECONDS}. Omit for the server default."
        ),
    )

    @field_validator("ciphertext")
    @classmethod
    def _check_byte_size(cls, value: str) -> str:
        # max_length counts characters; storage and the 64 KB cap are in bytes,
        # and one non-ASCII character can take up to four of them.
        if len(value.encode("utf-8")) > MAX_CIPHERTEXT_BYTES:
            raise ValueError(f"ciphertext exceeds {MAX_CIPHERTEXT_BYTES} bytes")
        return value


class SecretCreateResponse(BaseModel):
    payload_id: str
    ttl_seconds: int
    expires_at: datetime


class SecretRevealRequest(BaseModel):
    # Carried in the body rather than the path so the id never reaches an
    # access log, proxy log, or browser history (AUD-6).
    payload_id: str = Field(min_length=1, max_length=128)


class SecretExistsResponse(BaseModel):
    exists: bool


class SecretRetrieveResponse(BaseModel):
    recipient_id: str
    encrypted_keys: list[EncryptedKeyItem]
    iv: str
    ciphertext: str
