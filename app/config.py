from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields from .env
    )

    # Database
    DATABASE_HOST: str
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str

    # Security
    JWT_SIGNING_KEY: str  # HMAC-SHA256 signing only
    ENCRYPTION_KEY: str  # Field-level PII encryption only

    # Storage
    STORAGE_BACKEND: Literal["local", "s3"]
    STORAGE_LOCAL_PATH: str = "/data/resumes"
    RESUME_BUCKET_NAME: str = ""

    # Agent security
    AGENT_API_KEY: str
    INTERNAL_API_BASE_URL: str = "http://localhost:8000"

    # Metrics auth
    METRICS_USERNAME: str
    METRICS_PASSWORD: str

    # Portal
    PORTAL_TOKEN_TTL_DAYS: int = 7

    # Reporting
    INTERVIEW_LEADERBOARD_DEFAULT_PERIOD_DAYS: int = 30

    # AI model identifiers (optional with defaults)
    AI_RESUME_MODEL: str = "gemini-1.5-pro"
    AI_MATCHING_MODEL: str = "gemini-1.5-pro"
    AI_FEEDBACK_MODEL: str = "gemini-1.5-pro"

    # Application metadata
    APP_VERSION: str = "0.1.0"

    @field_validator(
        "JWT_SIGNING_KEY",
        "ENCRYPTION_KEY",
        "AGENT_API_KEY",
        "METRICS_USERNAME",
        "METRICS_PASSWORD",
        mode="before",
    )
    @classmethod
    def must_not_be_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty")
        return v

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )


settings = Settings()
