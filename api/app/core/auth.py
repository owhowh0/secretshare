import logging
from urllib.parse import urlparse, urlunparse

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


def _allowed_issuers(configured_issuer: str) -> list[str]:
    """Return configured issuer along with standard default-port equivalents (e.g. :80 or :443)."""
    iss = configured_issuer.rstrip("/")
    issuers = {iss}
    parsed = urlparse(iss)
    if parsed.scheme == "http" and parsed.port == 80:
        netloc = parsed.hostname or ""
        issuers.add(urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)).rstrip("/"))
    elif parsed.scheme == "https" and parsed.port == 443:
        netloc = parsed.hostname or ""
        issuers.add(urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)).rstrip("/"))
    elif parsed.port is None and parsed.hostname:
        default_port = 80 if parsed.scheme == "http" else (443 if parsed.scheme == "https" else None)
        if default_port:
            netloc = f"{parsed.hostname}:{default_port}"
            issuers.add(urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)).rstrip("/"))
    return list(issuers)


def get_jwks_client(settings: Settings = Depends(get_settings)) -> PyJWKClient:
    url = (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/certs"
    )
    client = _jwks_clients.get(url)
    if client is None:
        # PyJWT's default is 30 s; a hung Keycloak would hold every
        # authenticated request that long before the 503.
        client = PyJWKClient(
            url, cache_jwk_set=True, lifespan=3600, timeout=settings.jwks_timeout_seconds
        )
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
        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "audience": settings.keycloak_client_id,
        }
        if settings.keycloak_issuer:
            decode_kwargs["issuer"] = _allowed_issuers(settings.keycloak_issuer)
        claims = jwt.decode(token, signing_key.key, **decode_kwargs)
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
