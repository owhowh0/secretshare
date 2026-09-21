"""Centralized configuration: every runtime knob comes from Settings.

Covers defaults, env/.env loading, type validation, the derived root path, the
production fail-fast check, and that the routes actually use the configured
TTL and rate limits instead of hardcoded values.
"""

import pytest
from app.api.routes.secrets import get_audit_service
from app.core.config import Settings, get_settings
from app.main import app
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Every field Settings reads, so a developer's shell or .env cannot leak into
# the assertions about defaults.
_SETTINGS_ENV = [
    "ENVIRONMENT",
    "API_ROOT_PATH",
    "PR_NUMBER",
    "KEYCLOAK_URL",
    "KEYCLOAK_REALM",
    "KEYCLOAK_CLIENT_ID",
    "DATABASE_URL",
    "REDIS_URL",
    "AUDIT_ENABLED",
    "SECRET_TTL_SECONDS",
    "SECRET_TTL_MIN_SECONDS",
    "SECRET_TTL_MAX_SECONDS",
    "MAX_PAYLOAD_BYTES",
    "RATE_LIMIT_WINDOW_SECONDS",
    "CREATE_RATE_LIMIT",
    "RETRIEVE_RATE_LIMIT",
    "ALLOWED_ORIGINS",
]


@pytest.fixture
def clean_env(monkeypatch):
    for name in _SETTINGS_ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _settings(**kwargs) -> Settings:
    # _env_file=None keeps a stray .env in the working directory out of the test.
    return Settings(_env_file=None, **kwargs)


class TestDefaults:
    def test_defaults(self, clean_env):
        settings = _settings()

        assert settings.environment == "development"
        assert settings.secret_ttl_seconds == 600
        assert settings.secret_ttl_min_seconds == 300
        assert settings.secret_ttl_max_seconds == 86400
        assert settings.max_payload_bytes == 65536
        assert settings.rate_limit_window_seconds == 60
        assert settings.create_rate_limit == 10
        assert settings.retrieve_rate_limit == 30
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.database_url == ""
        assert settings.audit_enabled is True
        assert settings.root_path == "/api"


class TestEnvironmentLoading:
    def test_values_come_from_environment(self, clean_env):
        clean_env.setenv("SECRET_TTL_SECONDS", "420")
        clean_env.setenv("CREATE_RATE_LIMIT", "3")
        clean_env.setenv("REDIS_URL", "redis://cache:6379/2")
        clean_env.setenv("AUDIT_ENABLED", "false")
        clean_env.setenv("ALLOWED_ORIGINS", '["https://example.com"]')

        settings = _settings()

        assert settings.secret_ttl_seconds == 420
        assert settings.create_rate_limit == 3
        assert settings.redis_url == "redis://cache:6379/2"
        assert settings.audit_enabled is False
        assert settings.allowed_origins == ["https://example.com"]

    def test_values_come_from_env_file(self, clean_env, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("SECRET_TTL_SECONDS=900\nRETRIEVE_RATE_LIMIT=5\n")

        settings = Settings(_env_file=env_file)

        assert settings.secret_ttl_seconds == 900
        assert settings.retrieve_rate_limit == 5

    def test_environment_beats_env_file(self, clean_env, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("SECRET_TTL_SECONDS=900\n")
        clean_env.setenv("SECRET_TTL_SECONDS", "300")

        assert Settings(_env_file=env_file).secret_ttl_seconds == 300


class TestValidation:
    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("SECRET_TTL_SECONDS", "0"),
            ("SECRET_TTL_SECONDS", "-5"),
            ("SECRET_TTL_SECONDS", "ten"),
            ("MAX_PAYLOAD_BYTES", "0"),
            ("CREATE_RATE_LIMIT", "0"),
            ("RATE_LIMIT_WINDOW_SECONDS", "-1"),
            ("PR_NUMBER", "abc"),
            ("ENVIRONMENT", "staging-ish"),
        ],
    )
    def test_invalid_values_are_rejected(self, clean_env, name, value):
        clean_env.setenv(name, value)

        with pytest.raises(ValidationError):
            _settings()


class TestTtlBounds:
    def test_default_outside_bounds_is_rejected(self, clean_env):
        with pytest.raises(ValidationError, match="secret TTL bounds"):
            _settings(secret_ttl_seconds=100)

    def test_min_above_max_is_rejected(self, clean_env):
        with pytest.raises(ValidationError, match="secret TTL bounds"):
            _settings(
                secret_ttl_min_seconds=1000,
                secret_ttl_seconds=1000,
                secret_ttl_max_seconds=500,
            )

    def test_bounds_from_environment(self, clean_env):
        clean_env.setenv("SECRET_TTL_MIN_SECONDS", "60")
        clean_env.setenv("SECRET_TTL_MAX_SECONDS", "3600")

        settings = _settings()

        assert (settings.secret_ttl_min_seconds, settings.secret_ttl_max_seconds) == (60, 3600)


class TestRootPath:
    def test_preview_root_path_derived_from_pr_number(self, clean_env):
        clean_env.setenv("PR_NUMBER", "42")

        assert _settings().root_path == "/pr-42/api"

    def test_explicit_root_path_wins(self, clean_env):
        clean_env.setenv("PR_NUMBER", "42")
        clean_env.setenv("API_ROOT_PATH", "/custom/api")

        assert _settings().root_path == "/custom/api"

    def test_empty_root_path_is_respected(self, clean_env):
        clean_env.setenv("API_ROOT_PATH", "")

        assert _settings().root_path == ""


class TestProductionFailFast:
    def test_production_requires_datastores_and_oidc(self, clean_env):
        with pytest.raises(ValidationError) as exc_info:
            _settings(environment="production")

        message = str(exc_info.value)
        for name in ("database_url", "keycloak_url", "keycloak_realm", "keycloak_client_id"):
            assert name in message

    def test_complete_production_config_is_accepted(self, clean_env):
        settings = _settings(
            environment="production",
            database_url="postgresql+asyncpg://u:p@db/app",
            keycloak_url="http://keycloak:8080",
            keycloak_realm="secretshare",
            keycloak_client_id="secretshare-api",
        )

        assert settings.environment == "production"

    def test_development_tolerates_missing_dependencies(self, clean_env):
        assert _settings(environment="development").database_url == ""


# ---------------------------------------------------------------------------
# Routes pick the values up from Settings
# ---------------------------------------------------------------------------


class RecordingRedis:
    """Just enough Redis for SecretStore and the rate limiter."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.expiries: dict[str, int] = {}
        self.counters: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value
        self.expiries[key] = ex

    async def getdel(self, key: str) -> str | None:
        return self.data.pop(key, None)

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expiries[key] = seconds

    async def ttl(self, key: str) -> int:
        return self.expiries.get(key, -1)


class NullAuditService:
    async def record(self, *args, **kwargs) -> None:
        return None


@pytest.fixture
def make_client():
    had_redis = hasattr(app.state, "redis")
    previous = app.state.redis if had_redis else None
    redis = RecordingRedis()

    def _make(settings: Settings) -> tuple[TestClient, RecordingRedis]:
        app.state.redis = redis
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_audit_service] = lambda: NullAuditService()
        return TestClient(app), redis

    yield _make

    app.dependency_overrides.clear()
    if had_redis:
        app.state.redis = previous
    else:
        del app.state.redis


class TestRoutesUseSettings:
    def test_secret_ttl_comes_from_settings(self, make_client):
        client, redis = make_client(_settings(secret_ttl_seconds=450))

        payload_id = client.post("/secrets", json={"ciphertext": "abc"}).json()["payload_id"]

        assert redis.expiries[f"s:{payload_id}"] == 450

    def test_create_rate_limit_comes_from_settings(self, make_client):
        client, redis = make_client(
            _settings(create_rate_limit=2, rate_limit_window_seconds=17)
        )

        codes = [
            client.post("/secrets", json={"ciphertext": "abc"}).status_code
            for _ in range(3)
        ]

        assert codes == [201, 201, 429]
        limited = client.post("/secrets", json={"ciphertext": "abc"})
        assert limited.headers["retry-after"] == "17"

    def test_retrieve_rate_limit_comes_from_settings(self, make_client):
        client, _ = make_client(_settings(retrieve_rate_limit=1))

        first = client.post("/secrets/reveal", json={"payload_id": "missing"})
        second = client.post("/secrets/reveal", json={"payload_id": "missing"})

        assert first.status_code == 404
        assert second.status_code == 429
