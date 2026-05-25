import time
import logging
from collections import defaultdict
from typing import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def _clean_bucket(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        self._clean_bucket(key, now)
        return len(self._buckets[key]) < self.max_requests

    def record(self, key: str) -> None:
        self._buckets[key].append(time.time())


rate_limiter = RateLimiter(max_requests=120, window_seconds=60)


class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        client_ip = request.client.host if request.client else "unknown"

        if not rate_limiter.is_allowed(client_ip):
            logger.warning("Rate limit exceeded for %s", client_ip)
            response = JSONResponse(
                {"error": "Too many requests"}, status_code=429
            )
            await response(scope, receive, send)
            return

        rate_limiter.record(client_ip)
        await self.app(scope, receive, send)


class CallConcurrencyGuard:
    _active_calls: dict[str, int] = defaultdict(int)
    MAX_CONCURRENT = 3

    @classmethod
    def acquire(cls, customer_id: str) -> bool:
        if cls._active_calls.get(customer_id, 0) >= cls.MAX_CONCURRENT:
            return False
        cls._active_calls[customer_id] = cls._active_calls.get(customer_id, 0) + 1
        return True

    @classmethod
    def release(cls, customer_id: str) -> None:
        cls._active_calls[customer_id] = max(0, cls._active_calls.get(customer_id, 0) - 1)
        if cls._active_calls[customer_id] == 0:
            del cls._active_calls[customer_id]
