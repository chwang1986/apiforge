"""ApiForge Request ID middleware.

Assigns a unique ID to each request for tracing and correlation.
If the client sends an X-Request-ID header, it's preserved;
otherwise, a new UUID is generated.

The request ID is:
- Added to the response as X-Request-ID header
- Available in error responses (already handled by errors.py)
- Logged in request logs (already handled by logging middleware)

Usage:
    forge = ApiForge(name="MyService", request_id=True)

Or manually:
    from src.middleware.request_id import enable_request_id
    enable_request_id(app)
"""

from __future__ import annotations

import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Header name
REQUEST_ID_HEADER = "X-Request-ID"


def generate_request_id() -> str:
    """Generate a short unique request ID (12 hex chars)."""
    return uuid.uuid4().hex[:12]


class RequestIDMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that assigns a unique ID to each request.

    Behavior:
    - If request has X-Request-ID header, use it (preserves client's ID)
    - Otherwise, generate a new one
    - Always adds X-Request-ID to the response
    - Stores the ID in request.state for downstream access

    Args:
        app: The ASGI application.
        skip_paths: Paths to exclude (e.g. docs).
    """

    def __init__(
        self,
        app: Any,
        skip_paths: tuple[str, ...] = ("/api/docs", "/api/redoc"),
    ) -> None:
        super().__init__(app)
        self.skip_paths = set(skip_paths)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # Preserve client's request ID or generate new one
        request_id = request.headers.get(REQUEST_ID_HEADER) or generate_request_id()

        # Store for downstream access (middleware, handlers, error handlers)
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def enable_request_id(app: Any) -> None:
    """Enable request ID middleware on the FastAPI app.

    Args:
        app: The FastAPI application.
    """
    app.add_middleware(RequestIDMiddleware)
