from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Keycloak / OIDC
    keycloak_url: str = ""        # e.g. http://keycloak:8080
    keycloak_realm: str = ""      # e.g. secretshare
    keycloak_client_id: str = ""  # e.g. secretshare-api

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
