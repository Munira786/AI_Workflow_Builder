from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # Database: SQLite for zero-setup local dev, PostgreSQL in Docker/production.
    database_url: str = "sqlite:///./dev.db"

    # Job queue. When unset, runs execute in-process (fine for local dev and tests).
    redis_url: str | None = None
    run_queue_name: str = "runs"
    run_job_timeout_seconds: int = 600

    # Auth
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    jwt_algorithm: str = "HS256"

    # CORS: comma-separated list of allowed frontend origins.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Request limits
    max_nodes: int = 200
    max_edges: int = 500

    # LLM node (ANTHROPIC_API_KEY is read directly by the Anthropic SDK)
    llm_model: str = "claude-opus-5-5"
    llm_effort: str = "medium"
    llm_max_tokens: int = 16000
    llm_timeout_seconds: float = 120.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def normalize_postgres_scheme(cls, value: str) -> str:
        # Hosting providers often hand out postgres:// URLs; SQLAlchemy + psycopg 3 needs this form.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
