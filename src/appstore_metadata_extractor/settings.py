"""Global settings for the application."""

from functools import lru_cache
from typing import Optional

from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings with WBS boundaries."""

    # Application
    app_name: str = "AppStore Metadata Extractor"
    app_version: str = "0.1.0"
    debug: bool = False

    # API Settings
    api_prefix: str = "/api/v1"

    # Security
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15  # WBS boundary
    refresh_token_expire_days: int = 30  # WBS boundary

    # Database
    database_url: str = "sqlite+aiosqlite:///appstore.db"

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # Email (optional for now)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: str = "noreply@appstore-metadata.com"

    # Rate limiting (WBS boundaries)
    max_login_attempts_per_hour: int = 5
    max_registration_per_ip_per_day: int = 10
    password_reset_cooldown_minutes: int = 5
    email_verification_resend_minutes: int = 15

    # Performance (WBS boundaries)
    max_response_time_ms: int = 200
    max_db_query_time_ms: int = 100
    max_memory_per_request_mb: int = 100
    max_concurrent_users: int = 1000

    # Password requirements (WBS boundaries)
    password_min_length: int = 8
    bcrypt_rounds: int = 12

    # Note: For env file support in standalone package, users can override
    # settings by creating a Settings instance with custom values


def get_settings() -> Settings:
    """Get settings instance (cached in production, fresh in testing)."""
    import os

    if os.getenv("TESTING", "0") == "1":
        # Always return fresh settings in testing mode
        return Settings()
    # Use cached version in production
    return _get_cached_settings()


@lru_cache()
def _get_cached_settings() -> Settings:
    """Internal cached settings getter."""
    return Settings()


# Global settings instance
settings = get_settings()
