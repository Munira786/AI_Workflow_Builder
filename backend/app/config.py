from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Substrings found in the placeholder/dev keys shipped in this repo (.env.example,
# docker-compose.yml). A key containing one of them is public knowledge, whatever its length.
INSECURE_SECRET_MARKERS = ("change-me", "changeme", "replace-with", "dev-only", "example")
MIN_SECRET_LENGTH = 32


def _split_csv(value):
    if isinstance(value, str) and not value.startswith("["):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


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
    max_body_bytes: int = 1_000_000
    max_nodes: int = 200
    max_edges: int = 500
    max_field_chars: int = 50_000  # any single string inside a node's data (e.g. a template)

    # Rate limits: requests per window, per client IP (auth) or per user (runs).
    rate_limit_login: int = 5
    rate_limit_login_window_seconds: int = 60
    rate_limit_register: int = 5
    rate_limit_register_window_seconds: int = 3600
    rate_limit_runs: int = 20
    rate_limit_runs_window_seconds: int = 60

    # Quotas (cost control). 0 disables a quota.
    max_llm_nodes_per_run: int = 10
    max_active_runs_per_user: int = 3
    daily_token_budget_per_user: int = 1_000_000

    # LLM node
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5-5"
    llm_allowed_models: Annotated[list[str], NoDecode] = []  # llm_model is always allowed
    llm_effort: str = "medium"
    llm_max_tokens: int = 16000
    llm_timeout_seconds: float = 120.0  # max wait between streamed chunks, not total time
    llm_max_retries: int = 2

    # Observability
    log_level: str = "INFO"
    log_format: str | None = None  # "json" or "text"; default: json in production
    sentry_dsn: str | None = None

    @field_validator("cors_origins", "llm_allowed_models", mode="before")
    @classmethod
    def split_csv(cls, value):
        return _split_csv(value)

    @field_validator("database_url")
    @classmethod
    def normalize_postgres_scheme(cls, value: str) -> str:
        # Hosting providers often hand out postgres:// URLs; SQLAlchemy + psycopg 3 needs this form.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @model_validator(mode="after")
    def check_production_secret(self) -> "Settings":
        if self.is_production:
            key = self.secret_key
            if len(key) < MIN_SECRET_LENGTH or any(
                marker in key.lower() for marker in INSECURE_SECRET_MARKERS
            ):
                raise ValueError(
                    "SECRET_KEY must be a random value of at least 32 characters in production "
                    "(the placeholder and development keys in this repository are rejected). "
                    "Generate one with: "
                    'python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def allowed_models(self) -> list[str]:
        return list(dict.fromkeys([self.llm_model, *self.llm_allowed_models]))

    @property
    def json_logs(self) -> bool:
        if self.log_format:
            return self.log_format.lower() == "json"
        return self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
