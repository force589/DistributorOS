from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "testing", "preview", "production"] = "development"
    database_url: str
    database_migration_url: str | None = None
    database_admin_url: str | None = None
    database_pool_size: int = Field(default=3, ge=1, le=20)
    database_max_overflow: int = Field(default=2, ge=0, le=20)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=7200)
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_issuer: str = "distributoros-api"
    jwt_audience: str = "distributoros-mobile"
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    cors_origins: list[str] = ["http://localhost:8081", "http://localhost:19006"]
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    invoice_pdf_root: str = "storage/invoices"
    password_reset_url_base: str = "http://localhost:8081/reset-password"  # noqa: S105
    password_reset_minutes: int = Field(default=30, ge=10, le=120)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True
    rate_limit_enabled: bool = True
    login_rate_limit: int = Field(default=10, ge=1, le=1000)
    signup_rate_limit: int = Field(default=5, ge=1, le=1000)
    refresh_rate_limit: int = Field(default=30, ge=1, le=2000)
    search_rate_limit: int = Field(default=60, ge=1, le=5000)
    refresh_grace_seconds: int = Field(default=5, ge=1, le=15)

    @field_validator("database_url", "database_migration_url", "database_admin_url", mode="before")
    @classmethod
    def normalize_postgresql_url(cls, value: Any, info: object) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        field_name = getattr(info, "field_name", "database URL")
        raw_value = str(value).strip()
        if raw_value.startswith("postgres://"):
            raw_value = raw_value.replace("postgres://", "postgresql://", 1)
        try:
            parsed = make_url(raw_value)
        except Exception as exc:
            raise ValueError(f"{field_name.upper()} must be a valid PostgreSQL URL.") from exc
        if parsed.drivername == "postgresql":
            parsed = parsed.set(drivername="postgresql+asyncpg")
        if parsed.drivername != "postgresql+asyncpg":
            raise ValueError(
                f"{field_name.upper()} must use PostgreSQL with the asyncpg driver."
            )
        parsed = _normalize_asyncpg_ssl_query(parsed)
        return parsed.render_as_string(hide_password=False)

    @field_validator("cookie_secure")
    @classmethod
    def require_secure_production_cookie(cls, value: bool, info: object) -> bool:
        data = getattr(info, "data", {})
        if data.get("environment") == "production" and not value:
            raise ValueError("COOKIE_SECURE must be true in production.")
        return value

    @model_validator(mode="after")
    def require_production_web_origins(self) -> "Settings":
        if any(origin == "*" for origin in self.cors_origins):
            raise ValueError("CORS_ORIGINS must not contain wildcard origins.")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true.")
        if self.environment in {"preview", "production"}:
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS must contain the deployed web origin.")
            if any(
                origin.startswith(("http://localhost", "http://127.0.0.1"))
                for origin in self.cors_origins
            ):
                raise ValueError(
                    "CORS_ORIGINS must not contain local development origins "
                    "in preview or production."
                )
            if any(not origin.startswith("https://") for origin in self.cors_origins):
                raise ValueError(
                    "CORS_ORIGINS must use HTTPS origins in preview and production."
                )
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in preview and production.")
            if not self.password_reset_url_base.startswith("https://"):
                raise ValueError(
                    "PASSWORD_RESET_URL_BASE must use HTTPS in preview and production."
                )
        if self.environment == "production":
            missing_smtp = [
                name
                for name, value in {
                    "SMTP_HOST": self.smtp_host,
                    "SMTP_FROM_EMAIL": self.smtp_from_email,
                }.items()
                if not value
            ]
            if missing_smtp:
                raise ValueError(
                    f"Production password delivery requires: {', '.join(missing_smtp)}."
                )
        return self


def _normalize_asyncpg_ssl_query(parsed: URL) -> URL:
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    if sslmode is not None and "ssl" not in query:
        query["ssl"] = sslmode
    if query == dict(parsed.query):
        return parsed
    return parsed.set(query=query)


@lru_cache
def get_settings() -> Settings:
    return Settings()
