"""HTTP mapping for the secret domain exceptions."""

from fastapi import FastAPI, Request, status
from starlette.responses import JSONResponse

from app.services.exceptions import (
    InvalidSecretTTLError,
    SecretNotFoundError,
    SecretStoreUnavailableError,
)

# One body for every miss (unknown, burned, expired), so the response carries no
# enumeration oracle (invariant 5).
SECRET_NOT_FOUND_DETAIL = "Secret not found or already retrieved"
SECRET_STORE_UNAVAILABLE_DETAIL = "Secret storage is temporarily unavailable"

# Tells a well-behaved client when to try again after a store outage.
STORE_RETRY_AFTER_SECONDS = 5


async def _secret_not_found(request: Request, exc: SecretNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": SECRET_NOT_FOUND_DETAIL},
    )


async def _invalid_ttl(request: Request, exc: InvalidSecretTTLError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


async def _store_unavailable(
    request: Request, exc: SecretStoreUnavailableError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": SECRET_STORE_UNAVAILABLE_DETAIL},
        headers={"Retry-After": str(STORE_RETRY_AFTER_SECONDS)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(SecretNotFoundError, _secret_not_found)
    app.add_exception_handler(InvalidSecretTTLError, _invalid_ttl)
    app.add_exception_handler(SecretStoreUnavailableError, _store_unavailable)
