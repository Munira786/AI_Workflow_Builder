from app.config import Settings


def test_cors_origins_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://app.example.com")
    assert Settings().cors_origins == ["http://localhost:3000", "https://app.example.com"]


def test_postgres_url_normalized(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    assert Settings().database_url == "postgresql+psycopg://u:p@host:5432/db"
