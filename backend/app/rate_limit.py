"""Fixed-window rate limiting.

Time is cut into windows of `window_seconds`; each (key, window) pair has a counter and a
request is rejected once its counter passes `limit`, until the next window starts.

Two backends with the same interface:
  - MemoryRateLimiter: counters in this process. Used without Redis (local dev, tests); with
    several API processes each would count separately.
  - RedisRateLimiter: counters shared by every API process through Redis.

Limits are keyed by client IP (login, register) or by user (runs). The client IP is
`request.client.host`, which uvicorn rewrites from X-Forwarded-For only for proxies listed in
FORWARDED_ALLOW_IPS, so a client cannot spoof it and, behind a load balancer, each user gets
their own counter instead of everyone sharing the balancer's address.
"""

import logging
import math
import threading
import time
from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status

from app.config import get_settings
from app.models import User
from app.security import get_current_user

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised by a limiter when a key is over its limit."""

    def __init__(self, retry_after: int):
        super().__init__(f"Rate limit exceeded, retry after {retry_after}s")
        self.retry_after = retry_after  # whole seconds until the current window ends (>= 1)


def _retry_after(now: float, window: int, window_seconds: int) -> int:
    return max(1, math.ceil((window + 1) * window_seconds - now))


class MemoryRateLimiter:
    """In-process fixed-window limiter. `clock` is injectable so tests can fake time."""

    PURGE_INTERVAL_SECONDS = 60

    def __init__(self, clock: Callable[[], float] = time.time):
        self.clock = clock
        # (key, window_seconds, window number) -> count
        self._counts: dict[tuple[str, int, int], int] = {}
        self._lock = threading.Lock()  # sync endpoints run in a thread pool
        self._last_purge = clock()

    def hit(self, key: str, limit: int, window_seconds: int) -> None:
        now = self.clock()
        window = int(now // window_seconds)
        counter = (key, window_seconds, window)
        with self._lock:
            self._purge_expired(now)
            count = self._counts.get(counter, 0) + 1
            self._counts[counter] = count
        if count > limit:
            raise RateLimitExceeded(_retry_after(now, window, window_seconds))

    def _purge_expired(self, now: float) -> None:
        """Drop counters of finished windows so memory doesn't grow forever."""
        if now - self._last_purge < self.PURGE_INTERVAL_SECONDS:
            return
        self._last_purge = now
        expired = [
            counter for counter in self._counts
            if (counter[2] + 1) * counter[1] <= now
        ]
        for counter in expired:
            del self._counts[counter]


class RedisRateLimiter:
    """Fixed-window limiter backed by Redis, shared by every API process."""

    def __init__(self, redis_url: str, clock: Callable[[], float] = time.time):
        from redis import Redis

        self.redis = Redis.from_url(redis_url, socket_timeout=2, socket_connect_timeout=2)
        self.clock = clock

    def hit(self, key: str, limit: int, window_seconds: int) -> None:
        now = self.clock()
        window = int(now // window_seconds)
        redis_key = f"rl:{key}:{window}"
        # INCR and EXPIRE in one MULTI/EXEC transaction: a crash between them can't leave a
        # counter without an expiry.
        with self.redis.pipeline() as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds)
            count = pipe.execute()[0]
        if count > limit:
            raise RateLimitExceeded(_retry_after(now, window, window_seconds))


@lru_cache
def get_rate_limiter() -> MemoryRateLimiter | RedisRateLimiter:
    settings = get_settings()
    if settings.redis_url:
        return RedisRateLimiter(settings.redis_url)
    return MemoryRateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check(key: str, limit: int, window_seconds: int) -> None:
    try:
        get_rate_limiter().hit(key, limit, window_seconds)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, please slow down",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except Exception:
        # Redis unreachable: let the request through rather than take the API down with it.
        logger.exception("Rate limiter unavailable; allowing request")


def rate_limit(name: str, limit_setting: str) -> Callable[[Request], None]:
    """Dependency limiting requests per client IP. `limit_setting` names a Settings field;
    its window is the field of the same name with `_window_seconds` appended."""

    def dependency(request: Request) -> None:
        settings = get_settings()
        _check(
            f"{name}:ip:{client_ip(request)}",
            getattr(settings, limit_setting),
            getattr(settings, f"{limit_setting}_window_seconds"),
        )

    return dependency


def rate_limit_per_user(name: str, limit_setting: str) -> Callable[..., None]:
    """Dependency limiting requests per authenticated user (users behind one NAT don't collide)."""

    def dependency(user: User = Depends(get_current_user)) -> None:
        settings = get_settings()
        _check(
            f"{name}:user:{user.id}",
            getattr(settings, limit_setting),
            getattr(settings, f"{limit_setting}_window_seconds"),
        )

    return dependency
