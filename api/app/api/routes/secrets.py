from app.core.audit import AuditService
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiter
from app.schemas.secrets import (
    SecretCreateRequest,
    SecretCreateResponse,
    SecretExistsResponse,
    SecretRetrieveResponse,
    SecretRevealRequest,
)
from app.services.exceptions import SecretAccessDeniedError, SecretNotFoundError
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
    return SecretService(
        SecretStore(request.app.state.redis),
        default_ttl_seconds=settings.secret_ttl_seconds,
        min_ttl_seconds=settings.secret_ttl_min_seconds,
        max_ttl_seconds=settings.secret_ttl_max_seconds,
    )


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
    created = await service.create_secret(
        recipient_id=payload.recipient_id,
        encrypted_keys=payload.encrypted_keys,
        iv=payload.iv,
        ciphertext=payload.ciphertext,
        ttl_seconds=payload.ttl_seconds,
    )

    await audit.record(
        "created",
        payload_id=created.payload_id,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return SecretCreateResponse(
        payload_id=created.payload_id,
        ttl_seconds=created.ttl_seconds,
        expires_at=created.expires_at,
    )


@router.get(
    "/{payload_id}/exists",
    response_model=SecretExistsResponse,
    dependencies=[Depends(retrieve_rate_limit)],
)
async def check_secret_exists(
    payload_id: str,
    service: SecretService = Depends(get_secret_service),
) -> SecretExistsResponse:
    exists = await service.check_exists(payload_id)
    return SecretExistsResponse(exists=exists)


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
    claims: dict = Depends(get_current_user),
    service: SecretService = Depends(get_secret_service),
    audit: AuditService = Depends(get_audit_service),
) -> SecretRetrieveResponse:
    caller_identity = claims.get("preferred_username") or claims.get("sub")
    if not caller_identity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated token missing user identifier.",
        )

    payload_id = payload.payload_id
    try:
        envelope = await service.retrieve_secret(
            payload_id, caller_identity=caller_identity
        )
    except (SecretNotFoundError, SecretAccessDeniedError):
        # Audited here, then re-raised for the domain handler to turn into 404 / 403.
        await audit.record(
            "denied",
            payload_id=payload_id,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        raise

    await audit.record(
        "revealed",
        payload_id=payload_id,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return SecretRetrieveResponse(
        recipient_id=envelope.recipient_id,
        encrypted_keys=envelope.encrypted_keys,
        iv=envelope.iv,
        ciphertext=envelope.ciphertext,
    )
