import httpx
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import Settings, get_settings

_bearer = HTTPBearer()

# Simple in-process JWKS cache — refreshed on first request after startup.
_jwks_cache: dict | None = None


async def _fetch_jwks(settings: Settings) -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    url = (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache


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
        jwks = await _fetch_jwks(settings)
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims
