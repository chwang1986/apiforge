"""ApiForge security headers middleware.

Adds security-related HTTP headers to every response:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security (HSTS)
- Referrer-Policy
- Permissions-Policy

Usage:
    forge = ApiForge(name="MyService", security_headers=True)

Or manually:
    from src.middleware.security import enable_security_headers
    enable_security_headers(app)
"""

from __future__ import annotations

from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that adds security headers to all responses.

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: max-age=31536000; includeSubDomains
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: camera=(), microphone=(), geolocation=()

    Args:
        app: The ASGI application.
        hsts_max_age: HSTS max-age in seconds (default: 1 year).
        hsts_subdomains: Include subdomains in HSTS.
        frame_options: X-Frame-Options value (DENY or SAMEORIGIN).
        skip_paths: Paths to exclude.
    """

    def __init__(
        self,
        app: Any,
        hsts_max_age: int = 31536000,
        hsts_subdomains: bool = True,
        frame_options: str = "DENY",
        skip_paths: tuple[str, ...] = ("/api/docs", "/api/redoc"),
    ) -> None:
        super().__init__(app)
        self.hsts_max_age = hsts_max_age
        self.hsts_subdomains = hsts_subdomains
        self.frame_options = frame_options
        self.skip_paths = set(skip_paths)

    def _security_headers(self) -> dict[str, str]:
        """Build the security headers dict."""
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": self.frame_options,
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }

        if self.hsts_max_age > 0:
            hsts = f"max-age={self.hsts_max_age}"
            if self.hsts_subdomains:
                hsts += "; includeSubDomains"
            headers["Strict-Transport-Security"] = hsts

        return headers

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.skip_paths:
            return await call_next(request)

        response = await call_next(request)

        # Only add security headers for HTTPS or localhost (HSTS is HTTPS-only)
        is_https = request.headers.get("x-forwarded-proto", "") == "https"
        is_localhost = "localhost" in request.url.netloc or "127.0.0.1" in request.url.netloc

        for key, value in self._security_headers().items():
            # Skip HSTS for non-HTTPS requests (unless localhost for dev)
            if key == "Strict-Transport-Security" and not (is_https or is_localhost):
                continue
            response.headers[key] = value

        return response


def enable_security_headers(
    app: Any,
    hsts_max_age: int = 31536000,
    frame_options: str = "DENY",
) -> None:
    """Enable security headers on the FastAPI app.

    Args:
        app: The FastAPI application.
        hsts_max_age: HSTS max-age in seconds.
        frame_options: X-Frame-Options value.
    """
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_max_age=hsts_max_age,
        frame_options=frame_options,
    )
