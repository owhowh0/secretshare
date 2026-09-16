import jwt
from jwt import PyJWKClient, PyJWTError
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWKSetError
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import Settings, get_settings

_bearer = HTTPBearer()

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token signing key not found: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable.",
        ) from exc
