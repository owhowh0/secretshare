from app.core.audit import AuditService
from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiter
from app.schemas.secrets import (
    SecretCreateRequest,
    SecretCreateResponse,
    SecretRevealRequest,
    SecretRetrieveResponse,
)
from app.services.secrets import SecretService
from app.storage.redis_store import SecretStore
from fastapi import APIRouter, Depends, HTTPException, Request, status

router = APIRouter(
    prefix="/secrets",
    tags=["Secrets"],
)

create_rate_limit = RateLimiter(
    scope="secrets:create", limit_of=lambda s: s.create_rate_limit
)
retrieve_rate_limit = RateLimiter(
    scope="secrets:retrieve", limit_of=lambda s: s.retrieve_rate_limit
)


def get_secret_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> SecretService:
    store = SecretStore(request.app.state.redis, ttl_seconds=settings.secret_ttl_seconds)
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


# The payload id is the capability that unlocks a secret, so it travels in the
# request body, never in the URL path (AUD-6). A path id is copied verbatim into
# uvicorn's access log, proxy logs, and browser history, which would put a live
# capability in plaintext next to the audit row that deliberately truncates it.
@router.post(
    "/reveal",
    response_model=SecretRetrieveResponse,
    dependencies=[Depends(retrieve_rate_limit)],
)
async def reveal_secret(
    request: Request,
    payload: SecretRevealRequest,
    service: SecretService = Depends(get_secret_service),
    audit: AuditService = Depends(get_audit_service),
) -> SecretRetrieveResponse:
    payload_id = payload.payload_id
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
