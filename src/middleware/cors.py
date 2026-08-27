"""ApiForge CORS middleware configuration.

Provides sensible CORS defaults and a one-liner to enable CORS.

Usage:
    forge = ApiForge(name="MyService", cors_origins=["https://example.com"])

Or manually:
    from src.middleware.cors import enable_cors
    enable_cors(app, origins=["*"])
"""

from __future__ import annotations

from typing import Any

from fastapi.middleware.cors import CORSMiddleware


def enable_cors(
    app: Any,
    origins: list[str] | None = None,
    methods: list[str] | None = None,
    headers: list[str] | None = None,
    allow_credentials: bool = True,
    max_age: int = 86400,
) -> None:
    """Enable CORS on the FastAPI app.

    Args:
        app: The FastAPI application.
        origins: Allowed origins. Default ["*"].
        methods: Allowed HTTP methods. Default ["GET", "POST", "PUT", "DELETE", "OPTIONS"].
        headers: Allowed headers. Default ["*"].
        allow_credentials: Allow cookies/auth headers.
        max_age: Preflight cache duration in seconds.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=allow_credentials,
        allow_methods=methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=headers or ["*"],
        max_age=max_age,
    )
