"""AUD-6 — a payload id must never reach a log file.

The id is the capability that unlocks a secret, so anything that writes it in
plaintext defeats burn-after-read for whoever can read logs or backups. Two
layers are asserted here: the reveal route keeps the id out of the request line
altogether, and `RedactSecretPaths` scrubs it from anything that still manages
to log a `/secrets/<id>` path.
"""

import logging

import pytest
from app.core.auth import get_current_user
from app.api.routes.secrets import get_audit_service, get_secret_service
from app.core.ids import new_payload_id
from app.core.logging_filters import RedactSecretPaths, install_secret_path_redaction
from app.main import app
from tests.fakes import make_secret_service, recipient_claims, secret_body
from fastapi.testclient import TestClient

CIPHERTEXT = "ZmFrZS1jaXBoZXJ0ZXh0LXBheWxvYWQ"


class NullAuditService:
    async def record(self, *args, **kwargs) -> None:
        return None


class FakeRedis:
    """Enough of a Redis for the rate limiter; these tests are not about limits."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None

    async def ttl(self, key: str) -> int:
        return 60


@pytest.fixture
def client():
    secrets = make_secret_service()
    app.dependency_overrides[get_secret_service] = lambda: secrets
    app.dependency_overrides[get_audit_service] = lambda: NullAuditService()
    app.dependency_overrides[get_current_user] = recipient_claims

    # The rate limiter reads app.state.redis, which only the lifespan sets.
    # Restored afterwards so this fixture cannot change how other suites run.
    had_redis = hasattr(app.state, "redis")
    previous = app.state.redis if had_redis else None
    app.state.redis = FakeRedis()

    yield TestClient(app)

    app.dependency_overrides.clear()
    if had_redis:
        app.state.redis = previous
    else:
        del app.state.redis


class TestIdNeverReachesTheRequestLine:
    def test_reveal_keeps_the_id_out_of_the_url(self, client) -> None:
        payload_id = client.post(
            "/secrets", json=secret_body(CIPHERTEXT)
        ).json()["payload_id"]

        revealed = client.post("/secrets/reveal", json={"payload_id": payload_id})

        assert revealed.status_code == 200
        assert revealed.json()["ciphertext"] == CIPHERTEXT
        # This is the whole point of the route: uvicorn logs the request line,
        # and the request line is now id-free.
        assert payload_id not in str(revealed.request.url)

    def test_the_id_bearing_get_route_is_gone(self, client) -> None:
        payload_id = client.post(
            "/secrets", json=secret_body(CIPHERTEXT)
        ).json()["payload_id"]

        # No route matches an id in the path any more, so nothing can put one
        # in a request line. The secret itself stays revealable via POST.
        assert client.get(f"/secrets/{payload_id}").status_code == 404
        assert (
            client.post("/secrets/reveal", json={"payload_id": payload_id}).status_code
            == 200
        )


    def test_exists_keeps_the_id_out_of_the_url(self, client) -> None:
        payload_id = client.post(
            "/secrets", json=secret_body(CIPHERTEXT)
        ).json()["payload_id"]

        checked = client.post("/secrets/exists", json={"payload_id": payload_id})

        assert checked.status_code == 200
        assert checked.json() == {"exists": True}
        assert payload_id not in str(checked.request.url)
        # The old id-in-path form is gone.
        assert client.get(f"/secrets/{payload_id}/exists").status_code in (404, 405)

    def test_no_route_takes_a_payload_id_in_the_path(self) -> None:
        # Guards every current and future route, not just the ones above.
        offenders = [
            route.path
            for route in app.routes
            if "{" in getattr(route, "path", "") and "secret" in route.path
        ]
        assert offenders == []


class TestAccessLogRedaction:
    """Simulates what uvicorn.access emits: the path arrives as a format arg."""

    def test_full_id_is_absent_from_a_captured_access_log(self, caplog) -> None:
        install_secret_path_redaction()
        payload_id = new_payload_id()
        access = logging.getLogger("uvicorn.access")

        with caplog.at_level(logging.INFO, logger="uvicorn.access"):
            access.info(
                '%s - "%s %s HTTP/%s" %d',
                "127.0.0.1",
                "GET",
                f"/secrets/{payload_id}",
                "1.1",
                200,
            )

        assert payload_id not in caplog.text
        assert "/secrets/<redacted>" in caplog.text

    def test_exception_handler_paths_are_redacted(self, caplog) -> None:
        install_secret_path_redaction()
        payload_id = new_payload_id()
        api_logger = logging.getLogger("secretshare.api")

        with caplog.at_level(logging.ERROR, logger="secretshare.api"):
            api_logger.error(f"Unhandled error processing GET /secrets/{payload_id}: x")

        assert payload_id not in caplog.text

    def test_filter_leaves_ordinary_records_alone(self) -> None:
        record = logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1, "GET /health 200", None, None
        )

        assert RedactSecretPaths().filter(record) is True
        assert record.msg == "GET /health 200"

    def test_reveal_route_itself_is_not_redacted(self) -> None:
        record = logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            __file__,
            1,
            'POST /secrets/reveal HTTP/1.1" 200',
            None,
            None,
        )

        RedactSecretPaths().filter(record)

        assert record.msg == 'POST /secrets/reveal HTTP/1.1" 200'

    def test_installation_is_idempotent(self) -> None:
        install_secret_path_redaction()
        install_secret_path_redaction()

        filters = logging.getLogger("uvicorn.access").filters

        assert sum(isinstance(f, RedactSecretPaths) for f in filters) == 1
