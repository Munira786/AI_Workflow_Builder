"""Rate limiting: the limiter itself, and the limits wired into the API.

Default limits:
  - POST /api/v1/auth/login     5 requests per 60s     per client IP
  - POST /api/v1/auth/register  5 requests per 3600s   per client IP
  - POST /api/v1/runs           20 requests per 60s    per logged-in USER (not IP)
"""

import pytest

from app.rate_limit import MemoryRateLimiter, RateLimitExceeded, get_rate_limiter
from tests.conftest import register


class FakeClock:
    """Lets tests move time forward instantly instead of sleeping."""

    def __init__(self, now: float = 1_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    """API-level tests use a limiter with a frozen clock, so a slow test run can't straddle a
    window boundary (which would reset the count and make the limits look broken)."""
    limiter = MemoryRateLimiter(clock=FakeClock(now=1_000_010.0))
    monkeypatch.setattr("app.rate_limit.get_rate_limiter", lambda: limiter)
    return limiter


# ---------- The limiter itself (app/rate_limit.py) ----------
# (conftest.py resets the shared limiter before every test.)


def test_allows_up_to_the_limit():
    limiter = MemoryRateLimiter(clock=FakeClock())
    for _ in range(3):
        limiter.hit("k", limit=3, window_seconds=60)  # must not raise


def test_rejects_over_the_limit():
    limiter = MemoryRateLimiter(clock=FakeClock())
    for _ in range(3):
        limiter.hit("k", limit=3, window_seconds=60)
    with pytest.raises(RateLimitExceeded):
        limiter.hit("k", limit=3, window_seconds=60)


def test_retry_after_is_time_left_in_window():
    clock = FakeClock(now=600.0 + 45.5)  # 45.5s into a 60s window that started at 600
    limiter = MemoryRateLimiter(clock=clock)
    limiter.hit("k", limit=1, window_seconds=60)
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.hit("k", limit=1, window_seconds=60)
    assert exc_info.value.retry_after == 15  # 14.5s left, rounded UP


def test_new_window_resets_the_count():
    clock = FakeClock(now=600.0)
    limiter = MemoryRateLimiter(clock=clock)
    limiter.hit("k", limit=1, window_seconds=60)
    clock.now += 60  # next window
    limiter.hit("k", limit=1, window_seconds=60)  # allowed again


def test_keys_are_independent():
    limiter = MemoryRateLimiter(clock=FakeClock())
    limiter.hit("alice", limit=1, window_seconds=60)
    limiter.hit("bob", limit=1, window_seconds=60)  # bob has his own counter


def test_expired_windows_are_purged():
    clock = FakeClock(now=600.0)
    limiter = MemoryRateLimiter(clock=clock)
    for i in range(50):
        limiter.hit(f"client-{i}", limit=5, window_seconds=60)
    clock.now += 3600  # long after those windows ended
    limiter.hit("new-client", limit=5, window_seconds=60)
    assert len(limiter._counts) == 1


def test_limiter_outage_does_not_block_requests(client, monkeypatch):
    class Broken:
        def hit(self, *args):
            raise ConnectionError("redis down")

    monkeypatch.setattr("app.rate_limit.get_rate_limiter", lambda: Broken())
    register(client)  # still 201


def test_memory_limiter_used_without_redis():
    assert isinstance(get_rate_limiter(), MemoryRateLimiter)


# ---------- Wired into the API (routers) ----------


def login(client, email="user@example.com", password="wrong-password"):
    return client.post("/api/v1/auth/login", data={"username": email, "password": password})


def test_login_is_limited_to_5_per_minute(client):
    register(client)
    for _ in range(5):
        assert login(client).status_code == 401  # wrong password, but not blocked yet
    response = login(client)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1


def test_correct_password_is_also_blocked_when_limited(client):
    # Otherwise an attacker learns the password the moment they get a non-429 answer.
    register(client)
    for _ in range(5):
        login(client)
    assert login(client, password="password123").status_code == 429


def test_register_is_limited_to_5_per_hour(client):
    for i in range(5):
        register(client, f"user{i}@example.com")
    response = client.post(
        "/api/v1/auth/register", json={"email": "user9@example.com", "password": "password123"}
    )
    assert response.status_code == 429


def test_runs_are_limited_per_user_not_per_ip(client):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")  # same test client = same IP as alice
    graph = {"nodes": [{"id": "text-1", "type": "text", "data": {"text": "hi"}}], "edges": []}

    for _ in range(20):
        assert client.post("/api/v1/runs", json={"graph": graph}, headers=alice).status_code == 202
    assert client.post("/api/v1/runs", json={"graph": graph}, headers=alice).status_code == 429

    # Bob shares alice's IP but is a different user, so he is not affected.
    assert client.post("/api/v1/runs", json={"graph": graph}, headers=bob).status_code == 202


# ---------- Redis backend (shared by every API process) ----------


@pytest.fixture
def redis_limiter():
    import fakeredis

    from app.rate_limit import RedisRateLimiter

    clock = FakeClock(now=600.0)
    limiter = RedisRateLimiter.__new__(RedisRateLimiter)
    limiter.redis = fakeredis.FakeRedis()
    limiter.clock = clock
    return limiter, clock


def test_redis_limiter_counts_and_resets(redis_limiter):
    limiter, clock = redis_limiter
    for _ in range(3):
        limiter.hit("k", limit=3, window_seconds=60)
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.hit("k", limit=3, window_seconds=60)
    assert exc_info.value.retry_after == 60
    clock.now += 60
    limiter.hit("k", limit=3, window_seconds=60)  # new window


def test_redis_counters_expire(redis_limiter):
    limiter, _ = redis_limiter
    limiter.hit("k", limit=3, window_seconds=60)
    ttl = limiter.redis.ttl("rl:k:10")
    assert 0 < ttl <= 60
