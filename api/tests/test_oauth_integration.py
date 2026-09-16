import os
import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import app

pytestmark = pytest.mark.integration

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:80/keycloak").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "secretshare")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "secretshare-api")
TEST_USERNAME = os.getenv("TEST_USER_USERNAME", "testuser")
TEST_PASSWORD = os.getenv("TEST_USER_PASSWORD", "testpassword123")
TEST_EMAIL = os.getenv("TEST_USER_EMAIL", "test@example.com")
API_BASE_URL = os.getenv("API_BASE_URL", "")
REQUIRE_KEYCLOAK = os.getenv("REQUIRE_KEYCLOAK", "").lower() in ("1", "true", "yes")


async def is_keycloak_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}")
            return r.status_code == 200
    except Exception:
        return False


@pytest_asyncio.fixture(autouse=True)
async def check_keycloak():
    available = await is_keycloak_available()
    if not available:
        if REQUIRE_KEYCLOAK:
            pytest.fail(f"Keycloak is required but unreachable at {KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}")
        else:
            pytest.skip(f"Keycloak not reachable at {KEYCLOAK_URL}. Skipping live integration tests.")


@pytest_asyncio.fixture
async def api_client():
    if API_BASE_URL:
        host = os.getenv("API_HOST", "api.localhost")
        headers = {"Host": host}
        async with httpx.AsyncClient(base_url=API_BASE_URL, headers=headers, timeout=10) as client:
            yield client
    else:
        def _live_settings():
            return Settings(
                keycloak_url=KEYCLOAK_URL,
                keycloak_realm=KEYCLOAK_REALM,
                keycloak_client_id=KEYCLOAK_CLIENT_ID,
            )

        app.dependency_overrides[get_settings] = _live_settings
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def user_token() -> str:
    token_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            token_url,
            data={
                "client_id": KEYCLOAK_CLIENT_ID,
                "grant_type": "password",
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
                "scope": "openid",
            },
        )
        assert resp.status_code == 200, f"Token request failed: {resp.text}"
        data = resp.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]


class TestOAuthLiveIntegration:
    async def test_live_token_me_endpoint_returns_user_claims(self, api_client, user_token):
        """Authenticates with Keycloak, calls /me, and verifies decoded token claims."""
        resp = await api_client.get("/me", headers={"Authorization": f"Bearer {user_token}"})
        assert resp.status_code == 200, f"Unexpected response: {resp.status_code} - {resp.text}"
        claims = resp.json()

        assert claims.get("preferred_username") == TEST_USERNAME
        assert claims.get("email") == TEST_EMAIL
        assert claims.get("email_verified") is True
        assert "sub" in claims

    async def test_missing_token_returns_403(self, api_client):
        """Missing Authorization header on /me returns 403."""
        resp = await api_client.get("/me")
        assert resp.status_code == 403

    async def test_invalid_token_returns_401(self, api_client):
        """Malformed token on /me returns 401."""
        resp = await api_client.get("/me", headers={"Authorization": "Bearer invalid.fake.token"})
        assert resp.status_code == 401

    async def test_tampered_token_returns_401(self, api_client, user_token):
        """Tampered signature on /me returns 401."""
        tampered_token = user_token[:-5] + "XXXXX"
        resp = await api_client.get("/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert resp.status_code == 401
