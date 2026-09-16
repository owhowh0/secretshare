import logging

import jwt
from jwt import PyJWKClient, PyJWTError
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWKSetError
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import Settings, get_settings

logger = logging.getLogger("secretshare.auth")

_bearer = HTTPBearer()

# Every rejected token gets this one message. Naming the reason — an unknown
# signing key, a bad audience, an expired token — tells an attacker probing for
# a forgery which part of their token to fix next, so the reason is logged
# server-side and never returned (brief §2).
_INVALID_TOKEN_DETAIL = "Invalid or expired token"

_jwks_clients: dict[str, PyJWKClient] = {}


def get_jwks_client(settings: Settings = Depends(get_settings)) -> PyJWKClient:
    url = (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/certs"
    )
    client = _jwks_clients.get(url)
    if client is None:
        client = PyJWKClient(url, cache_jwk_set=True, lifespan=3600)
        _jwks_clients[url] = client
    return client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    settings: Settings = Depends(get_settings),
    jwks_client: PyJWKClient = Depends(get_jwks_client),
) -> dict:
    """
    Validates the Bearer JWT against Keycloak's public keys using PyJWT.
    Returns the decoded token claims on success.
    """
    if not settings.keycloak_url or not settings.keycloak_realm:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth is not configured on this server.",
        )
    token = credentials.credentials
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
        )
        return claims
    except (PyJWKClientConnectionError, ConnectionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable.",
        ) from exc
    except (PyJWKClientError, PyJWKSetError) as exc:
        # The token itself is never logged: it is a bearer credential, and
        # invariant 6 keeps credentials out of the logs.
        logger.warning("Token rejected: signing key lookup failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except PyJWTError as exc:
        logger.warning("Token rejected: %s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        # Unexpected failures were previously silent; without this the cause of a
        # 503 is unrecoverable after the fact.
        logger.exception("Unexpected error during token validation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable.",
        ) from exc
