from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Keycloak / OIDC
    keycloak_url: str = ""  # e.g. http://keycloak:8080
    keycloak_realm: str = ""  # e.g. secretshare
    keycloak_client_id: str = ""  # e.g. secretshare-api

    # CORS
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
