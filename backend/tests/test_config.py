import pytest
from pydantic import ValidationError

from app.config import Settings


def test_cors_origins_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://app.example.com")
    assert Settings().cors_origins == ["http://localhost:3000", "https://app.example.com"]


def test_postgres_url_normalized(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    assert Settings().database_url == "postgresql+psycopg://u:p@host:5432/db"


@pytest.mark.parametrize(
    "key",
    [
        "short",
        "change-me-in-production",
        "dev-only-secret-key-change-me-0123456789",  # docker-compose.yml fallback
        'replace-with-output-of: python -c "import secrets; print(secrets.token_urlsafe(48))"',
    ],
)
def test_production_rejects_known_or_weak_secret_keys(monkeypatch, key):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", key)
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings()


def test_production_accepts_a_random_secret_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "Zq3vX9yT1mK8pL2wR7nB4cD6fH0jS5aE-UoIiG")
    assert Settings().is_production


def test_allowed_models_always_include_the_default(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("LLM_ALLOWED_MODELS", "claude-sonnet-5-5, claude-haiku-5-5")
    assert Settings().allowed_models == ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
