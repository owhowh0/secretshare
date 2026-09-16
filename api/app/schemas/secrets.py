from pydantic import BaseModel, Field

from app.core.config import get_settings

# Resolved at import time so the limit appears in the OpenAPI schema. The
# server stays blind to the envelope's structure (invariant 1) — only the
# total size is judged, never the contents.
MAX_CIPHERTEXT_LENGTH = get_settings().max_payload_bytes


class SecretCreateRequest(BaseModel):
    ciphertext: str = Field(min_length=1, max_length=MAX_CIPHERTEXT_LENGTH)


class SecretCreateResponse(BaseModel):
    payload_id: str


class SecretRetrieveResponse(BaseModel):
    ciphertext: str
