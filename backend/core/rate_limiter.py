"""Simple in-memory rate limiter for guest mode."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request


class RateLimiter:
    """Token-bucket rate limiter keyed by client IP."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        self._requests[key] = [
            t for t in self._requests[key] if t > cutoff
        ]

    def check(self, request: Request) -> None:
        """Check rate limit for a request. Raises 429 if exceeded."""
        client_ip = request.client.host if request.client else "unknown"
        self._cleanup(client_ip)

        if len(self._requests[client_ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded. Maximum {self.max_requests} "
                    f"queries per {self.window_seconds} seconds. "
                    "Please wait before trying again."
                ),
            )

        self._requests[client_ip].append(time.time())

    @property
    def remaining(self) -> dict[str, int]:
        """Get remaining requests per IP (for debugging)."""
        result = {}
        for key in self._requests:
            self._cleanup(key)
            result[key] = max(
                0, self.max_requests - len(self._requests[key])
            )
        return result


rate_limiter = RateLimiter()
