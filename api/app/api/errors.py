"""HTTP mapping for the secret domain exceptions and request validation errors."""

from app.services.exceptions import (
    InvalidSecretTTLError,
    SecretAccessDeniedError,
    SecretNotFoundError,
    SecretStoreUnavailableError,
)
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

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


async def _secret_access_denied(
    request: Request, exc: SecretAccessDeniedError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": "You are not the intended recipient of this secret."},
    )


# Keys FastAPI's default 422 body carries per error. "input" is left out: it
# echoes the rejected value back, which for POST /secrets is up to 64 KB of the
# caller's ciphertext — and for a bad reveal, a payload id.
_VALIDATION_ERROR_KEYS = ("type", "loc", "msg", "ctx")


async def _request_validation(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {key: error[key] for key in _VALIDATION_ERROR_KEYS if key in error}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        # A custom validator's ValueError sits in ctx["error"]; its message is
        # ours (never the input), so render it instead of an empty object.
        content={"detail": jsonable_encoder(errors, custom_encoder={Exception: str})},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _request_validation)
    app.add_exception_handler(SecretNotFoundError, _secret_not_found)
    app.add_exception_handler(SecretAccessDeniedError, _secret_access_denied)
    app.add_exception_handler(InvalidSecretTTLError, _invalid_ttl)
    app.add_exception_handler(SecretStoreUnavailableError, _store_unavailable)
