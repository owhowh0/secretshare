from app.schemas.secrets import (
    SecretCreateRequest,
    SecretCreateResponse,
    SecretRetrieveResponse,
)
from app.services.secrets import SecretService
from app.storage.redis_store import SecretStore
from fastapi import APIRouter, Depends, HTTPException, Request, status

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


@router.get(
    "/{payload_id}",
    response_model=SecretRetrieveResponse,
)
async def retrieve_secret(
    payload_id: str,
    service: SecretService = Depends(get_secret_service),
) -> SecretRetrieveResponse:
    ciphertext = await service.retrieve_secret(payload_id)

    if ciphertext is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found or already retrieved",
        )

    return SecretRetrieveResponse(ciphertext=ciphertext)
