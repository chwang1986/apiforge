"""ApiForge request logging middleware.

Logs each request with method, path, status code, and elapsed time.
Supports both human-readable and structured JSON output.

Usage:
    forge = ApiForge(name="MyService", log_requests=True)

Or manually:
    from src.middleware.logging import RequestLoggerMiddleware
    app.add_middleware(RequestLoggerMiddleware)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Dedicated logger for request logs
request_logger = logging.getLogger("apiforge.requests")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that logs each request.

    Logs: method, path, status_code, elapsed_ms, client_ip
    Format: structured JSON or human-readable (configurable).

    Args:
        json_output: If True, output as JSON. If False, human-readable.
        include_path: Whether to log the full path (including query string).
        skip_paths: Paths to exclude from logging (e.g. health checks).
    """

    def __init__(
        self,
        app: Any,
        json_output: bool = False,
        include_path: bool = True,
        skip_paths: tuple[str, ...] = ("/health",),
    ) -> None:
        super().__init__(app)
        self.json_output = json_output
        self.include_path = include_path
        self.skip_paths = set(skip_paths)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip health checks and docs
        if request.url.path in self.skip_paths:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        client_ip = request.client.host if request.client else "unknown"
        log_path = request.url.path if self.include_path else request.url.path.split("?")[0]

        log_entry: dict[str, Any] = {
            "method": request.method,
            "path": log_path,
            "status": response.status_code,
            "elapsed_ms": round(elapsed_ms, 2),
            "client": client_ip,
        }

        if self.json_output:
            request_logger.info(json.dumps(log_entry, ensure_ascii=False))
        else:
            request_logger.info(
                "%s %s → %d (%.1fms) [%s]",
                log_entry["method"],
                log_entry["path"],
                log_entry["status"],
                log_entry["elapsed_ms"],
                log_entry["client"],
            )

        # Add response headers
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"
        return response


def enable_request_logging(
    app: Any,
    json_output: bool = False,
    level: int = logging.INFO,
) -> None:
    """Enable request logging on a FastAPI/Starlette app.

    Args:
        app: The FastAPI application.
        json_output: Output logs as JSON.
        level: Logging level (default INFO).
    """
    app.add_middleware(RequestLoggerMiddleware, json_output=json_output)

    # Ensure the logger has a handler
    if not request_logger.handlers:
        handler = logging.StreamHandler()
        if json_output:
            handler.setFormatter(logging.Formatter("%(message)s"))
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
            )
        request_logger.addHandler(handler)
        request_logger.setLevel(level)
        request_logger.propagate = False
