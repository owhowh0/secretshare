from fastapi import APIRouter, Depends, Request, status

from app.schemas.secrets import (
    SecretCreateRequest,
    SecretCreateResponse
)
from app.services.secrets import SecretService
from app.storage.redis_store import SecretStore

router = APIRouter(
    prefix="/secrets",
    tags=["Secrets"],
)


def get_secret_service(request: Request) -> SecretService:
    store = SecretStore(request.app.state.redis)
    return SecretService(store)

@router.post(
    "",
    response_model=SecretCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_secret(
    payload: SecretCreateRequest,
    service: SecretService = Depends(get_secret_service),
) -> SecretCreateResponse:
    payload_id = await service.create_secret(payload.ciphertext)
    return SecretCreateResponse(payload_id=payload_id)
