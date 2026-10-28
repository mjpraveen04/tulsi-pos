"""Application settings, read from the environment (README Section 10)."""

from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://tulsi:tulsi@localhost:5432/tulsi_pos"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    upi_id: str = "tulsitiffins@upi"
    upi_payee_name: str = "Tulsi Tiffins"

    # Uploaded product photos are stored in Postgres and served under this prefix.
    media_url_prefix: str = "/media"
    max_photo_bytes: int = 5 * 1024 * 1024
    photo_max_edge: int = 900

    gst_rate: Decimal = Decimal("0.05")

    # Browser origins allowed to call the API. The nginx container proxies /api
    # on the same origin, so this only matters for `npm run dev`.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
