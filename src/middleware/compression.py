"""ApiForge response compression middleware.

Gzip-compresses responses when the client supports it.
Wraps Starlette's built-in GZipMiddleware with sensible defaults.

Usage:
    forge = ApiForge(name="MyService", compress=True)

Or manually:
    from src.middleware.compression import enable_compression
    enable_compression(app, minimum_size=500)
"""

from __future__ import annotations

from typing import Any

from starlette.middleware.gzip import GZipMiddleware


# Minimum response size to compress (bytes)
# Below this, compression overhead > savings
DEFAULT_MINIMUM_SIZE = 500


def enable_compression(
    app: Any,
    minimum_size: int = DEFAULT_MINIMUM_SIZE,
) -> None:
    """Enable gzip compression on the FastAPI app.

    Only compresses responses:
    - Larger than minimum_size bytes
    - With content types that benefit (JSON, text, HTML, JS, CSS)
    - When client sends Accept-Encoding: gzip

    Args:
        app: The FastAPI application.
        minimum_size: Minimum response size in bytes to trigger compression.
    """
    app.add_middleware(GZipMiddleware, minimum_size=minimum_size)
