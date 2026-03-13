from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────
    app_env: str = "development"
    secret_key: str = "change-me"
    # Comma-separated origins string: "*" or "https://a.com,https://b.com"
    cors_origins: str = "*"

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_set(cls, v: str, info) -> str:
        # Prevent deploying with the default insecure key
        if v == "change-me":
            import os
            if os.getenv("APP_ENV", "development") == "production":
                raise ValueError(
                    "SECRET_KEY must be changed from the default value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
        return v

    @field_validator("app_env")
    @classmethod
    def app_env_must_be_valid(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}, got: {v!r}")
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/pantaubumi"

    @property
    def async_database_url(self) -> str:
        """
        Normalise the database URL to always use the asyncpg driver.

        Neon (and most PostgreSQL providers) give you a plain
        `postgresql://…` URL.  SQLAlchemy async requires
        `postgresql+asyncpg://`.  We also strip `channel_binding`
        which asyncpg does not understand.
        """
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

        url = self.database_url

        # Rewrite scheme
        for old in ("postgresql://", "postgres://"):
            if url.startswith(old):
                url = "postgresql+asyncpg://" + url[len(old):]
                break

        # Strip unsupported asyncpg query params
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params.pop("channel_binding", None)   # not supported by asyncpg

        # asyncpg uses ssl=require, not sslmode=require
        if "sslmode" in params:
            sslmode = params.pop("sslmode")[0]
            if sslmode in ("require", "verify-ca", "verify-full"):
                params["ssl"] = ["require"]

        new_query = urlencode({k: v[0] for k, v in params.items()})
        return urlunparse(parsed._replace(query=new_query))

    # ── External APIs ────────────────────────────────────────────
    bmkg_base_url: str = "https://data.bmkg.go.id/DataMKG/TEWS"
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    usgs_base_url: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    petabencana_base_url: str = "https://data.petabencana.id/floods/reports"

    # ── Firebase ─────────────────────────────────────────────────
    firebase_credentials_path: str = "firebase-credentials.json"
    firebase_credentials_json: str = ""  # Alternative: inline JSON string

    # ── Scheduler ────────────────────────────────────────────────
    ingestion_interval_minutes: int = 5

    # ── AI Model Paths ───────────────────────────────────────────
    flood_model_path: str = "app/ai/weights/flood_model.pkl"
    landslide_model_path: str = "app/ai/weights/landslide_model.pkl"


settings = Settings()
