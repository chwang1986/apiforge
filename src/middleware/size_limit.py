"""ApiForge payload size limit middleware.

Rejects requests with bodies larger than the configured limit.
Protects against DoS attacks via oversized payloads.

Usage:
    forge = ApiForge(name="MyService", max_body_bytes=1_048_576)  # 1 MB

Or manually:
    from src.middleware.size_limit import enable_size_limit
    enable_size_limit(app, max_bytes=524288)  # 512 KB
"""

from __future__ import annotations

from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse


DEFAULT_MAX_BYTES = 1_048_576  # 1 MB


class SizeLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that rejects oversized request bodies.

    Checks the Content-Length header. If absent (chunked transfer),
    the request is allowed through (can't determine size upfront).

    Args:
        app: The ASGI application.
        max_bytes: Maximum allowed body size in bytes.
        skip_paths: Paths to exclude.
    """

    def __init__(
        self,
        app: Any,
        max_bytes: int = DEFAULT_MAX_BYTES,
        skip_paths: tuple[str, ...] = ("/api/docs", "/api/redoc"),
    ) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes
        self.skip_paths = set(skip_paths)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Any:
        if request.url.path in self.skip_paths:
            return await call_next(request)

        content_length = request.headers.get("Content-Length")
        if content_length is not None:
            try:
                size = int(content_length)
            except (ValueError, TypeError):
                size = 0

            if size > self.max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": (
                                f"Request body too large. "
                                f"Max: {self.max_bytes} bytes, got: {size} bytes."
                            ),
                        }
                    },
                    headers={"Content-Length": str(size), "Accept-Ranges": "none"},
                )

        response = await call_next(request)
        return response


def enable_size_limit(app: Any, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
    """Enable payload size limit on the FastAPI app.

    Args:
        app: The FastAPI application.
        max_bytes: Maximum allowed body size in bytes.
    """
    app.add_middleware(SizeLimitMiddleware, max_bytes=max_bytes)
