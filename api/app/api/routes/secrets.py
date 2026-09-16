from app.core.audit import AuditService
from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiter
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

create_rate_limit = RateLimiter(limit=10, window_seconds=60, scope="secrets:create")
retrieve_rate_limit = RateLimiter(limit=30, window_seconds=60, scope="secrets:retrieve")


def get_secret_service(request: Request) -> SecretService:
    store = SecretStore(request.app.state.redis)
    return SecretService(store)


def get_audit_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AuditService:
    return AuditService(
        getattr(request.app.state, "db_session_factory", None),
        enabled=settings.audit_enabled,
    )


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "",
    response_model=SecretCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(create_rate_limit)],
)
async def create_secret(
    request: Request,
    payload: SecretCreateRequest,
    service: SecretService = Depends(get_secret_service),
    audit: AuditService = Depends(get_audit_service),
) -> SecretCreateResponse:
    payload_id = await service.create_secret(payload.ciphertext)

    await audit.record(
        "created",
        payload_id=payload_id,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return SecretCreateResponse(payload_id=payload_id)


@router.get(
    "/{payload_id}",
    response_model=SecretRetrieveResponse,
    dependencies=[Depends(retrieve_rate_limit)],
)
async def retrieve_secret(
    request: Request,
    payload_id: str,
    service: SecretService = Depends(get_secret_service),
    audit: AuditService = Depends(get_audit_service),
) -> SecretRetrieveResponse:
    ciphertext = await service.retrieve_secret(payload_id)

    await audit.record(
        "revealed" if ciphertext is not None else "denied",
        payload_id=payload_id,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    if ciphertext is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found or already retrieved",
        )

    return SecretRetrieveResponse(ciphertext=ciphertext)
