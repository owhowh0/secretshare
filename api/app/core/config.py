from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "production"]


class Settings(BaseSettings):
    """
    Single source of runtime configuration.

    Every value is read from the environment (or a .env file) by its field name,
    case-insensitively — `redis_url` comes from REDIS_URL. Nothing else in the
    app should call os.getenv.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Environment = "development"

    # Routing. The API sits behind Traefik under a path prefix; FastAPI needs it
    # to render correct Swagger and OpenAPI URLs.
    api_root_path: str | None = None  # explicit prefix, wins when set
    pr_number: int | None = Field(default=None, gt=0)  # set in preview stacks

    # Keycloak / OIDC
    keycloak_url: str = ""  # e.g. http://keycloak:8080
    keycloak_realm: str = ""  # e.g. secretshare
    keycloak_client_id: str = ""  # e.g. secretshare-api

    # Datastores
    database_url: str = ""  # postgresql+asyncpg://... ; empty disables audit logging
    redis_url: str = "redis://localhost:6379/0"

    # TLS – path to the CA certificate used to verify PostgreSQL and Redis
    # connections. Leave empty to connect without certificate verification.
    tls_ca_cert: str = ""

    # Audit
    audit_enabled: bool = True

    # Secrets. A secret expires on its own after secret_ttl_seconds if it is
    # never read; a client may ask for any lifetime within the min/max bounds.
    secret_ttl_seconds: int = Field(default=600, gt=0)
    secret_ttl_min_seconds: int = Field(default=300, gt=0)  # 5 minutes
    secret_ttl_max_seconds: int = Field(default=86400, gt=0)  # 24 hours

    # Payload limits. 64 KB per CLAUDE.md §7; the relay stays blind to the
    # envelope's contents, so total size is the only thing it may judge.
    max_payload_bytes: int = Field(default=65536, gt=0)

    # Rate limits, per client IP per window.
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    create_rate_limit: int = Field(default=10, gt=0)
    retrieve_rate_limit: int = Field(default=30, gt=0)

    # CORS
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @property
    def root_path(self) -> str:
        if self.api_root_path is not None:
            return self.api_root_path
        if self.pr_number is not None:
            return f"/pr-{self.pr_number}/api"
        return "/api"

    @model_validator(mode="after")
    def _check_ttl_bounds(self) -> "Settings":
        if not (
            self.secret_ttl_min_seconds
            <= self.secret_ttl_seconds
            <= self.secret_ttl_max_seconds
        ):
            raise ValueError(
                "secret TTL bounds must satisfy "
                "secret_ttl_min_seconds <= secret_ttl_seconds <= secret_ttl_max_seconds"
            )
        return self

    @model_validator(mode="after")
    def _require_production_dependencies(self) -> "Settings":
        # Outside production an empty value degrades gracefully (audit off, 503
        # on auth). In production that would be a silent misconfiguration, so it
        # fails at startup instead.
        if self.environment != "production":
            return self
        missing = [
            name
            for name in ("database_url", "keycloak_url", "keycloak_realm", "keycloak_client_id")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(
                "missing required settings for production: " + ", ".join(missing)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
