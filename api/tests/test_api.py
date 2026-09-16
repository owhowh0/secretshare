import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import make_token


# ---------------------------------------------------------------------------
# Unauthenticated endpoints
# ---------------------------------------------------------------------------
class TestHealthEndpoints:
    async def test_health_returns_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    async def test_root_returns_welcome(self, client):
        r = await client.get("/")
        assert r.status_code == 200
        assert "message" in r.json()


# ---------------------------------------------------------------------------
# /me — OAuth protected
# ---------------------------------------------------------------------------
class TestMeEndpoint:
    async def test_valid_token_returns_claims(self, client, private_key_pem):
        token = make_token(private_key_pem)
        r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["sub"] == "user-123"
        assert data["email"] == "test@example.com"
        assert data["preferred_username"] == "testuser"

    async def test_no_token_returns_403(self, client):
        # FastAPI's HTTPBearer returns 403 when the header is missing entirely
        r = await client.get("/me")
        assert r.status_code == 403

    async def test_expired_token_returns_401(self, client, private_key_pem):
        token = make_token(private_key_pem, exp_delta=-60)
        r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
        assert "Invalid token" in r.json()["detail"]

    async def test_wrong_audience_returns_401(self, client, private_key_pem):
        token = make_token(private_key_pem, audience="some-other-service")
        r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    async def test_unknown_kid_returns_401(self, client, private_key_pem):
        # Token is signed with our key but claims a kid that isn't in the JWKS
        token = make_token(private_key_pem, kid="unknown-kid-xyz")
        r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
        assert "signing key not found" in r.json()["detail"]

    async def test_garbage_token_returns_401(self, client):
        r = await client.get("/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401

    async def test_keycloak_unreachable_returns_503(
        self, client_no_keycloak, private_key_pem
    ):
        token = make_token(private_key_pem)
        r = await client_no_keycloak.get(
            "/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 503
        assert "unavailable" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Global Exception Handling
# ---------------------------------------------------------------------------
class TestErrorHandling:
    async def test_unhandled_exception_returns_500_without_leaking_traceback(self):
        from app.api.routes.secrets import get_secret_service
        from app.main import app

        def _crashing_service():
            raise RuntimeError("Database password leaked in raw traceback :(")

        app.dependency_overrides[get_secret_service] = _crashing_service

        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                r = await ac.get("/secrets/any-id")

                assert r.status_code == 500
                assert r.json() == {"detail": "Internal server error"}
                assert "password leaked" not in r.text
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
class TestCORS:
    async def test_cors_headers_present_for_allowed_origin(self, client):
        origin = "http://localhost:3000"
        r = await client.get("/health", headers={"Origin": origin})

        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == origin
        assert r.headers.get("access-control-allow-credentials") == "true"

    async def test_cors_preflight_options(self, client):
        origin = "http://localhost:3000"
        r = await client.options(
            "/secrets",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == origin
        assert "POST" in r.headers.get("access-control-allow-methods", "")
