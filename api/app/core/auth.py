import time
import httpx
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import Settings, get_settings

_bearer = HTTPBearer()

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600  # seconds; refresh after 1 hour even without a key miss


async def _fetch_jwks(settings: Settings, *, force: bool = False) -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    if (
        not force
        and _jwks_cache is not None
        and (now - _jwks_fetched_at) < _JWKS_TTL
    ):
        return _jwks_cache
    if not settings.keycloak_url or not settings.keycloak_realm:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth is not configured on this server.",
        )
    url = (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_fetched_at = now
    return _jwks_cache


async def _get_signing_key(token: str, settings: Settings) -> dict:
    """
    Returns the JWK whose kid matches the token header.
    On a cache miss, refreshes the JWKS once to handle key rotation.
    """
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")

    jwks = await _fetch_jwks(settings)
    key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)

    if key is None:
        # kid not in cache — Keycloak may have rotated keys, try a forced refresh
        jwks = await _fetch_jwks(settings, force=True)
        key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signing key not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return key


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Validates the Bearer JWT against Keycloak's public keys.
    Returns the decoded token claims on success.
    """
    token = credentials.credentials
    try:
        key = await _get_signing_key(token, settings)
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable.",
        ) from exc
    return claims
