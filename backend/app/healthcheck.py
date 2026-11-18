"""Dependency checks shared by GET /health and the worker's container healthcheck.

    python -m app.healthcheck     exit 0 when the database (and Redis, if configured) answer
"""

import sys

from sqlalchemy import text

from app.config import get_settings
from app.db import engine


def check_dependencies() -> dict[str, str]:
    """Return {"database": "ok" | "error", "redis": ...}. Never raises."""
    results: dict[str, str] = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        results["database"] = "ok"
    except Exception:
        results["database"] = "error"

    redis_url = get_settings().redis_url
    if redis_url:
        try:
            from redis import Redis

            Redis.from_url(redis_url, socket_timeout=2, socket_connect_timeout=2).ping()
            results["redis"] = "ok"
        except Exception:
            results["redis"] = "error"
    return results


if __name__ == "__main__":
    checks = check_dependencies()
    print(checks)
    sys.exit(0 if all(value == "ok" for value in checks.values()) else 1)
