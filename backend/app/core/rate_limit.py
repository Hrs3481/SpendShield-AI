"""
Fixed-window rate limiter for the auth endpoints.

Scope note, stated plainly: this counter lives in the process, so with N
backend replicas the effective limit is N x the configured value. That is
enough to stop credential stuffing from a single IP, which is what it is for.
A multi-replica deployment should move the counter to Redis — the
`RateLimiter.hit` signature is the only thing a Redis version has to match.
"""
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, attempts: int, window_seconds: int) -> None:
        self.attempts = attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Records an attempt. Returns False once the caller is over the limit."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            recent = [t for t in self._hits[key] if t > cutoff]
            recent.append(now)
            self._hits[key] = recent
            if len(self._hits) > 10_000:      # bound memory against IP-spray attacks
                self._evict(cutoff)
            return len(recent) <= self.attempts

    def _evict(self, cutoff: float) -> None:
        for key in [k for k, v in self._hits.items() if not any(t > cutoff for t in v)]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_ip(request: Request) -> str:
    """Trusts X-Forwarded-For's first hop — correct behind Render/Vercel/nginx."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _describe(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} seconds"
    minutes = round(seconds / 60)
    return "a minute" if minutes == 1 else f"{minutes} minutes"


def enforce(limiter: RateLimiter, request: Request) -> None:
    if not limiter.hit(client_ip(request)):
        # The wait quoted here is derived from the limiter's own window; a hard-coded
        # "wait a minute" was wrong for every limiter that isn't a 60-second one.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Please wait {_describe(limiter.window_seconds)} and try again.",
            headers={"Retry-After": str(limiter.window_seconds)},
        )
