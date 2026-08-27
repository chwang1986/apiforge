"""ApiForge rate limiting middleware (Token Bucket algorithm).

Limits the number of requests per client IP within a time window.
Uses in-memory storage (single-instance). For distributed setups,
swap the backend with Redis.

Usage:
    forge = ApiForge(name="MyService", rate_limit={"requests": 100, "window_seconds": 60})

Or manually:
    from src.middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, requests_per_window=100, window_seconds=60)
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse


@dataclass
class TokenBucket:
    """A single token bucket for rate limiting.

    Attributes:
        capacity: Maximum number of tokens (requests allowed in burst).
        refill_rate: Tokens added per second.
        tokens: Current token count.
        last_refill: Timestamp of last refill.
    """

    capacity: int
    refill_rate: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        """Try to consume one token. Returns True if allowed, False if rate limited."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    @property
    def retry_after_seconds(self) -> float:
        """Seconds until next token is available."""
        if self.tokens >= 1.0:
            return 0.0
        deficit = 1.0 - self.tokens
        return deficit / self.refill_rate if self.refill_rate > 0 else float("inf")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that rate-limits requests per client IP.

    Uses the Token Bucket algorithm:
    - Each IP gets a bucket with `capacity` tokens
    - Tokens refill at `refill_rate` per second
    - Each request consumes 1 token
    - When bucket is empty, request is rejected with 429

    Args:
        app: The ASGI application.
        requests_per_window: Max requests allowed in the window.
        window_seconds: Time window in seconds.
        skip_paths: Paths to exclude (e.g. health checks).
    """

    def __init__(
        self,
        app: Any,
        requests_per_window: int = 100,
        window_seconds: int = 60,
        skip_paths: tuple[str, ...] = ("/health",),
    ) -> None:
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.skip_paths = set(skip_paths)
        # Key: client IP → TokenBucket
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                capacity=requests_per_window,
                refill_rate=requests_per_window / window_seconds,
            )
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Any:
        # Skip health checks and docs
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # Identify client
        client_ip = request.client.host if request.client else "unknown"
        bucket = self._buckets[client_ip]

        if not bucket.consume():
            retry_after = max(1, int(bucket.retry_after_seconds))
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Rate limit exceeded. Try again in {retry_after}s.",
                        "retry_after": retry_after,
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        # Add rate limit info headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_window)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        return response


def enable_rate_limiting(
    app: Any,
    requests_per_window: int = 100,
    window_seconds: int = 60,
) -> None:
    """Enable rate limiting on the FastAPI app.

    Args:
        app: The FastAPI application.
        requests_per_window: Max requests per window per IP.
        window_seconds: Window duration in seconds.
    """
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_window=requests_per_window,
        window_seconds=window_seconds,
    )
