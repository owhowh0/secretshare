from pydantic import BaseModel, Field


class SecretCreateRequest(BaseModel):
    ciphertext: str = Field(min_length=1)


class SecretCreateResponse(BaseModel):
    payload_id: str