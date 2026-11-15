"""Configuration lue dans les variables d'environnement (ou un fichier .env).

Les valeurs par défaut suffisent en développement local avec `docker compose up db`.
"""

from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me-in-production-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://careneo:careneo@localhost:5432/careneo"

    jwt_secret: str = DEV_JWT_SECRET
    session_cookie_name: str = "careneo_session"
    session_ttl_minutes: int = 8 * 60
    cookie_secure: bool = False  # à activer derrière HTTPS

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> Self:
        if self.environment == "production" and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET doit être défini (32 caractères minimum) en production")
        return self


settings = Settings()
