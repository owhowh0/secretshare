"""Real client address behind trusted proxies (TrustedProxyMiddleware).

Behind Traefik the TCP peer is always the proxy. These tests pin down that
the rate limiter and audit see the forwarded client instead, and that nobody
can pick their own address by sending X-Forwarded-For.
"""

import re
from pathlib import Path

import pytest
import yaml
from app.api.routes.secrets import get_audit_service, get_secret_service
from app.core.config import Settings, get_settings
from app.core.proxy import TrustedProxyMiddleware
from app.main import app
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from tests.fakes import make_secret_service, secret_body

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
TRAEFIK = "172.18.0.3"


async def _echo(scope, receive, send):
    request = Request(scope, receive)
    response = JSONResponse(
        {"client": request.client.host if request.client else None, "scheme": request.url.scheme}
    )
    await response(scope, receive, send)


def _client(peer: str, trusted=PRIVATE) -> AsyncClient:
    wrapped = TrustedProxyMiddleware(_echo, trusted_proxies=trusted)
    return AsyncClient(
        transport=ASGITransport(app=wrapped, client=(peer, 40000)), base_url="http://test"
    )


async def _seen(peer: str, headers: dict | None = None, trusted=PRIVATE) -> dict:
    async with _client(peer, trusted) as client:
        return (await client.get("/", headers=headers or {})).json()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class TestClientResolution:
    async def test_forwarded_client_used_when_peer_is_trusted(self):
        seen = await _seen(TRAEFIK, {"X-Forwarded-For": "100.101.102.103"})
        assert seen["client"] == "100.101.102.103"

    async def test_headers_ignored_from_untrusted_peer(self):
        # A client talking to the API directly cannot claim another address.
        seen = await _seen("203.0.113.9", {"X-Forwarded-For": "1.2.3.4"})
        assert seen["client"] == "203.0.113.9"

    async def test_spoofed_leftmost_entry_is_ignored(self):
        # Client sent "1.2.3.4"; the sidecar appended the real tailnet IP and
        # Traefik appended the sidecar. The rightmost untrusted hop wins.
        seen = await _seen(
            TRAEFIK, {"X-Forwarded-For": "1.2.3.4, 100.101.102.103, 172.18.0.7"}
        )
        assert seen["client"] == "100.101.102.103"

    async def test_all_trusted_chain_uses_leftmost(self):
        seen = await _seen(TRAEFIK, {"X-Forwarded-For": "172.18.0.9, 172.18.0.7"})
        assert seen["client"] == "172.18.0.9"

    async def test_malformed_chain_keeps_the_peer(self):
        seen = await _seen(TRAEFIK, {"X-Forwarded-For": "100.101.102.103, not-an-ip"})
        assert seen["client"] == TRAEFIK

    async def test_no_header_keeps_the_peer(self):
        assert (await _seen(TRAEFIK))["client"] == TRAEFIK

    async def test_ipv6_client(self):
        seen = await _seen(TRAEFIK, {"X-Forwarded-For": "2001:db8::1"})
        assert seen["client"] == "2001:db8::1"

    async def test_default_trust_is_loopback_only(self):
        seen = await _seen(
            TRAEFIK, {"X-Forwarded-For": "100.101.102.103"}, trusted=["127.0.0.1/32"]
        )
        assert seen["client"] == TRAEFIK


class TestScheme:
    async def test_forwarded_proto_from_trusted_peer(self):
        seen = await _seen(TRAEFIK, {"X-Forwarded-Proto": "https"})
        assert seen["scheme"] == "https"

    async def test_forwarded_proto_from_untrusted_peer_ignored(self):
        seen = await _seen("203.0.113.9", {"X-Forwarded-Proto": "https"})
        assert seen["scheme"] == "http"

    async def test_bogus_proto_ignored(self):
        seen = await _seen(TRAEFIK, {"X-Forwarded-Proto": "javascript"})
        assert seen["scheme"] == "http"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestTrustedProxiesSetting:
    def test_default_is_loopback(self, monkeypatch):
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        assert Settings(_env_file=None).trusted_proxies == ["127.0.0.1/32", "::1/128"]

    def test_comma_separated_env(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8, 172.16.0.0/12,192.168.0.0/16")
        assert Settings(_env_file=None).trusted_proxies == PRIVATE

    def test_json_list_env(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXIES", '["172.18.0.0/16"]')
        assert Settings(_env_file=None).trusted_proxies == ["172.18.0.0/16"]

    @pytest.mark.parametrize("value", ["not-a-cidr", "10.0.0.0/33", "300.1.1.1"])
    def test_invalid_cidr_fails_at_startup(self, monkeypatch, value):
        monkeypatch.setenv("TRUSTED_PROXIES", value)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)


# ---------------------------------------------------------------------------
# End to end through the app: rate limit and audit see the real client
# ---------------------------------------------------------------------------


class CountingRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None

    async def ttl(self, key: str) -> int:
        return 60

    async def set(self, key, value, ex=None):
        return None


class RecordingAudit:
    def __init__(self) -> None:
        self.ips: list[str | None] = []

    async def record(self, event_type: str, *, ip=None, **kwargs) -> None:
        self.ips.append(ip)


@pytest.fixture
def app_behind_traefik():
    """The real app, wrapped as Traefik would reach it, with a 2/window limit."""
    had_redis = hasattr(app.state, "redis")
    previous = app.state.redis if had_redis else None
    redis = CountingRedis()
    audit = RecordingAudit()
    app.state.redis = redis
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, create_rate_limit=2
    )
    app.dependency_overrides[get_secret_service] = lambda: make_secret_service()
    app.dependency_overrides[get_audit_service] = lambda: audit
    wrapped = TrustedProxyMiddleware(app, trusted_proxies=PRIVATE)

    def client() -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=wrapped, client=(TRAEFIK, 40000)),
            base_url="http://test",
        )

    yield client, redis, audit

    app.dependency_overrides.clear()
    if had_redis:
        app.state.redis = previous
    else:
        del app.state.redis


class TestRateLimitPerRealClient:
    async def test_each_client_gets_its_own_bucket(self, app_behind_traefik):
        make, redis, _ = app_behind_traefik

        async def create(ip: str) -> int:
            async with make() as client:
                response = await client.post(
                    "/secrets", json=secret_body(), headers={"X-Forwarded-For": ip}
                )
                return response.status_code

        alice = [await create("100.64.0.1") for _ in range(3)]
        bob = [await create("100.64.0.2") for _ in range(2)]

        # Before the fix both shared the Traefik bucket: bob would be 429.
        assert alice == [201, 201, 429]
        assert bob == [201, 201]
        assert set(redis.counters) == {
            "rl:secrets:create:100.64.0.1",
            "rl:secrets:create:100.64.0.2",
        }

    async def test_spoofing_xff_does_not_reset_the_limit(self, app_behind_traefik):
        make, _, _ = app_behind_traefik
        codes = []
        for n in range(3):
            async with make() as client:
                response = await client.post(
                    "/secrets",
                    json=secret_body(),
                    # A fresh forged address each time, followed by the hop
                    # the proxy actually recorded.
                    headers={"X-Forwarded-For": f"9.9.9.{n}, 100.64.0.1"},
                )
                codes.append(response.status_code)

        assert codes == [201, 201, 429]

    async def test_audit_records_the_real_client(self, app_behind_traefik):
        make, _, audit = app_behind_traefik
        async with make() as client:
            await client.post(
                "/secrets", json=secret_body(), headers={"X-Forwarded-For": "100.64.0.1"}
            )

        assert audit.ips == ["100.64.0.1"]


# ---------------------------------------------------------------------------
# Deployment wiring
# ---------------------------------------------------------------------------


class TestDeploymentWiring:
    @pytest.mark.parametrize("compose", ["docker-compose.yml", "docker-compose.preview.yml"])
    def test_api_trusts_private_proxy_ranges(self, compose):
        data = yaml.safe_load((REPO_ROOT / compose).read_text(encoding="utf-8"))
        env = data["services"]["api"]["environment"]
        entries = env if isinstance(env, list) else [f"{k}={v}" for k, v in env.items()]
        value = next(e.split("=", 1)[1] for e in entries if e.startswith("TRUSTED_PROXIES="))

        assert Settings(_env_file=None, trusted_proxies=value).trusted_proxies == PRIVATE

    def test_uvicorn_leaves_forwarded_headers_to_the_app(self):
        dockerfile = (REPO_ROOT / "api" / "Dockerfile").read_text(encoding="utf-8")
        cmd = next(line for line in dockerfile.splitlines() if line.startswith("CMD"))

        assert "--no-proxy-headers" in cmd
        assert re.search(r"--proxy-headers\b", cmd.replace("--no-proxy-headers", "")) is None

    def test_preview_traefik_keeps_sidecar_forwarded_headers(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "deploy-preview.yml").read_text(
            encoding="utf-8"
        )

        assert '--entrypoints.web.forwardedHeaders.trustedIPs="${TRAEFIK_TRUSTED_IPS}"' in workflow
        assert 'TRAEFIK_TRUSTED_IPS="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"' in workflow
        # An already-running router without the flag must be replaced.
        assert "docker rm -f traefik" in workflow
