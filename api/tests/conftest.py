import base64
import time

import httpx
import pytest
import pytest_asyncio
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

import app.core.auth as auth_module
from app.core.config import Settings, get_settings
from app.main import app

# ---------------------------------------------------------------------------
# Constants used across all tests
# ---------------------------------------------------------------------------
TEST_KID = "test-key-id"
TEST_KEYCLOAK_URL = "http://keycloak-test:8080"
TEST_REALM = "test-realm"
TEST_CLIENT_ID = "secretshare-api"


# ---------------------------------------------------------------------------
# RSA key pair — generated once per test session (slow operation)
# ---------------------------------------------------------------------------
def _int_to_base64url(n: int) -> str:
    length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()


@pytest.fixture(scope="session")
def rsa_private_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )


@pytest.fixture(scope="session")
def private_key_pem(rsa_private_key) -> bytes:
    return rsa_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture(scope="session")
def jwks_document(rsa_private_key) -> dict:
    """A minimal JWKS document containing our test public key."""
    pub = rsa_private_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "kid": TEST_KID,
                "alg": "RS256",
                "n": _int_to_base64url(pub.n),
                "e": _int_to_base64url(pub.e),
            }
        ]
    }


# ---------------------------------------------------------------------------
# Token factory
# ---------------------------------------------------------------------------
def make_token(
    private_key_pem: bytes,
    *,
    audience: str = TEST_CLIENT_ID,
    exp_delta: int = 300,
    kid: str = TEST_KID,
    **extra_claims,
) -> str:
    """Signs a JWT with our test RSA private key."""
    from jose import jwt

    claims = {
        "sub": "user-123",
        "email": "test@example.com",
        "preferred_username": "testuser",
        "aud": audience,
        "iss": f"{TEST_KEYCLOAK_URL}/realms/{TEST_REALM}",
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_delta,
        **extra_claims,
    }
    return jwt.encode(claims, private_key_pem, algorithm="RS256", headers={"kid": kid})


# ---------------------------------------------------------------------------
# Test client fixtures
# ---------------------------------------------------------------------------
def _override_settings() -> Settings:
    return Settings(
        keycloak_url=TEST_KEYCLOAK_URL,
        keycloak_realm=TEST_REALM,
        keycloak_client_id=TEST_CLIENT_ID,
    )


@pytest_asyncio.fixture
async def client(monkeypatch, jwks_document):
    """
    AsyncClient with settings overridden and _fetch_jwks mocked
    to return our test JWKS document without hitting the network.
    """
    auth_module._jwks_cache = None
    auth_module._jwks_fetched_at = 0.0
    app.dependency_overrides[get_settings] = _override_settings

    async def _mock_fetch_jwks(settings, *, force=False):
        return jwks_document

    monkeypatch.setattr(auth_module, "_fetch_jwks", _mock_fetch_jwks)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_no_keycloak(monkeypatch):
    """
    Same as client but _fetch_jwks raises a connection error,
    simulating Keycloak being unreachable.
    """
    auth_module._jwks_cache = None
    auth_module._jwks_fetched_at = 0.0
    app.dependency_overrides[get_settings] = _override_settings

    async def _mock_fetch_jwks_fail(settings, *, force=False):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(auth_module, "_fetch_jwks", _mock_fetch_jwks_fail)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
