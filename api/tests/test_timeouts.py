"""Timeouts on every outbound dependency: Redis, PostgreSQL and the JWKS fetch.

The hung-Redis tests use a socket that listens but never accepts: the kernel
completes the TCP handshake, so the client connects, sends its command and then
waits for a reply that never comes. That is the failure a timeout must bound.
"""

import socket
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.routes.secrets import (
    create_rate_limit,
    get_audit_service,
    get_secret_service,
    retrieve_rate_limit,
)
from app.core.auth import _jwks_clients, get_jwks_client
from app.core.config import Settings
from app.db.session import create_engine
from app.main import app
from app.services.exceptions import SecretStoreUnavailableError
from app.storage.redis_store import SecretStore, create_redis_client
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tests.fakes import make_secret_service, secret_body

SOCKET_TIMEOUT = 0.3
# Generous upper bound so a slow CI runner does not flake; without a timeout
# these calls would block indefinitely, so any finite bound proves the point.
MAX_ELAPSED = 3.0


@pytest.fixture
def hung_redis_url():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    yield f"redis://127.0.0.1:{sock.getsockname()[1]}/0"
    sock.close()


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


class TestTimeoutSettings:
    def test_defaults_are_finite(self, monkeypatch):
        for name in (
            "REDIS_CONNECT_TIMEOUT_SECONDS",
            "REDIS_SOCKET_TIMEOUT_SECONDS",
            "DB_CONNECT_TIMEOUT_SECONDS",
            "DB_COMMAND_TIMEOUT_SECONDS",
            "DB_POOL_TIMEOUT_SECONDS",
            "JWKS_TIMEOUT_SECONDS",
        ):
            monkeypatch.delenv(name, raising=False)
        settings = _settings()
        assert settings.redis_connect_timeout_seconds == 3.0
        assert settings.redis_socket_timeout_seconds == 5.0
        assert settings.db_connect_timeout_seconds == 5.0
        assert settings.db_command_timeout_seconds == 10.0
        assert settings.db_pool_timeout_seconds == 10.0
        assert settings.jwks_timeout_seconds == 5.0

    def test_read_from_environment(self, monkeypatch):
        monkeypatch.setenv("REDIS_SOCKET_TIMEOUT_SECONDS", "1.5")
        monkeypatch.setenv("JWKS_TIMEOUT_SECONDS", "2")
        settings = _settings()
        assert settings.redis_socket_timeout_seconds == 1.5
        assert settings.jwks_timeout_seconds == 2.0

    @pytest.mark.parametrize("value", ["0", "-1"])
    def test_non_positive_timeout_rejected(self, value, monkeypatch):
        monkeypatch.setenv("REDIS_SOCKET_TIMEOUT_SECONDS", value)
        with pytest.raises(ValidationError):
            _settings()


class TestRedisClient:
    def test_timeouts_reach_the_connection(self):
        client = create_redis_client(
            "redis://redis:6379/0", connect_timeout=1.0, socket_timeout=2.0
        )
        kwargs = client.connection_pool.connection_kwargs
        assert kwargs["socket_connect_timeout"] == 1.0
        assert kwargs["socket_timeout"] == 2.0
        assert "ssl_ca_certs" not in kwargs

    def test_tls_kwargs_only_for_rediss(self, tmp_path):
        ca = tmp_path / "ca.crt"
        ca.write_text("unused: the client is never connected")
        client = create_redis_client(
            "rediss://redis:6379/0",
            tls_ca_cert=str(ca),
            connect_timeout=1.0,
            socket_timeout=2.0,
        )
        kwargs = client.connection_pool.connection_kwargs
        assert kwargs["ssl_ca_certs"] == str(ca)
        assert kwargs["ssl_cert_reqs"] == "required"
        assert kwargs["socket_timeout"] == 2.0

    async def test_hung_redis_fails_fast_as_store_unavailable(self, hung_redis_url):
        client = create_redis_client(
            hung_redis_url, connect_timeout=SOCKET_TIMEOUT, socket_timeout=SOCKET_TIMEOUT
        )
        service = make_secret_service(SecretStore(client))
        started = time.monotonic()
        try:
            with pytest.raises(SecretStoreUnavailableError):
                await service.check_exists("some-id")
        finally:
            await client.aclose()
        assert time.monotonic() - started < MAX_ELAPSED

    def test_hung_redis_returns_503_within_bound(self, hung_redis_url):
        client = create_redis_client(
            hung_redis_url, connect_timeout=SOCKET_TIMEOUT, socket_timeout=SOCKET_TIMEOUT
        )
        app.dependency_overrides[get_secret_service] = lambda: make_secret_service(
            SecretStore(client)
        )
        app.dependency_overrides[get_audit_service] = lambda: AsyncMock()
        app.dependency_overrides[create_rate_limit] = lambda: None
        app.dependency_overrides[retrieve_rate_limit] = lambda: None
        try:
            started = time.monotonic()
            response = TestClient(app).post("/secrets", json=secret_body())
            elapsed = time.monotonic() - started
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert response.headers["retry-after"]
        assert elapsed < MAX_ELAPSED


class TestDatabaseEngine:
    def _engine_kwargs(self, **kwargs) -> dict:
        with patch("app.db.session.create_async_engine") as mock:
            mock.return_value = MagicMock()
            create_engine("postgresql+asyncpg://u:p@db/app", **kwargs)
            _, engine_kwargs = mock.call_args
            return engine_kwargs

    def test_timeouts_passed_to_asyncpg_and_pool(self):
        kwargs = self._engine_kwargs(
            connect_timeout=4.0, command_timeout=9.0, pool_timeout=7.0
        )
        assert kwargs["connect_args"]["timeout"] == 4.0
        assert kwargs["connect_args"]["command_timeout"] == 9.0
        assert kwargs["pool_timeout"] == 7.0

    def test_unset_timeouts_leave_library_defaults(self):
        kwargs = self._engine_kwargs()
        assert "timeout" not in kwargs["connect_args"]
        assert "command_timeout" not in kwargs["connect_args"]
        assert "pool_timeout" not in kwargs


class TestJwksClient:
    def test_jwks_fetch_uses_configured_timeout(self):
        settings = _settings(
            keycloak_url="http://kc-timeout-test:8080",
            keycloak_realm="r",
            jwks_timeout_seconds=1.5,
        )
        try:
            client = get_jwks_client(settings)
            assert client.timeout == 1.5
        finally:
            _jwks_clients.pop(client.uri, None)
