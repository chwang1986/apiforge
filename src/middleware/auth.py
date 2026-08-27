"""ApiForge API Key authentication middleware.

Validates requests against a set of pre-registered API keys.
Keys are passed via the `Authorization: Bearer <key>` header
or the `X-API-Key` header.

Usage:
    forge = ApiForge(
        name="MyService",
        api_keys={"key-abc-123": "client-a", "key-xyz-789": "client-b"},
    )

Or with a key generator:
    from src.middleware.auth import generate_api_key
    key = generate_api_key()  # "aforge_8f3a2b1c9d4e5f6a7b8c9d0e1f2a3b4c"
"""

from __future__ import annotations

import secrets
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse


def generate_api_key(prefix: str = "aforge") -> str:
    """Generate a cryptographically secure API key.

    Returns:
        A key like "aforge_8f3a2b1c9d4e5f6a7b8c9d0e1f2a3b4c"
    """
    return f"{prefix}_{secrets.token_hex(16)}"


def hash_api_key(key: str) -> str:
    """Hash an API key for secure storage (SHA-256).

    In production, store only the hash. Compare hashes on validation.
    """
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that validates API keys on each request.

    Accepts keys via:
    - `Authorization: Bearer <key>` (preferred)
    - `X-API-Key: <key>` (alternative)

    Args:
        app: The ASGI application.
        api_keys: Dict mapping key → client name.
        skip_paths: Paths that don't require auth (e.g. health, docs).
        allow_hashed: If True, keys in api_keys dict may be pre-hashed (SHA-256).
    """

    def __init__(
        self,
        app: Any,
        api_keys: dict[str, str],
        skip_paths: tuple[str, ...] = (
            "/health",
            "/api/docs",
            "/api/redoc",
            "/api/openapi.json",
        ),
        allow_hashed: bool = False,
    ) -> None:
        super().__init__(app)
        self.api_keys = api_keys
        self.skip_paths = set(skip_paths)
        self.allow_hashed = allow_hashed
        self._key_set: set[str] = set(api_keys.keys())
        if allow_hashed:
            self._hashed_set: set[str] = {hash_api_key(k) for k in api_keys.keys()}
        else:
            self._hashed_set = set()

    def _extract_key(self, request: Request) -> str | None:
        """Extract API key from request headers."""
        # Try Authorization: Bearer <key>
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()

        # Try X-API-Key
        return request.headers.get("X-API-Key")

    def _validate_key(self, key: str) -> bool:
        """Check if key is valid (plain or hashed)."""
        if key in self._key_set:
            return True
        if self._hashed_set and hash_api_key(key) in self._hashed_set:
            return True
        return False

    def _client_name(self, key: str) -> str:
        """Get the client name for a key."""
        return self.api_keys.get(key, "unknown")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Any:
        # Skip public paths
        if request.url.path in self.skip_paths:
            return await call_next(request)

        key = self._extract_key(request)
        if key is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTH_MISSING",
                        "message": "API key required. Use 'Authorization: Bearer <key>' or 'X-API-Key' header.",
                    }
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not self._validate_key(key):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTH_INVALID",
                        "message": "Invalid API key.",
                    }
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Request is authorized
        response = await call_next(request)
        response.headers["X-Authenticated-Client"] = self._client_name(key)
        return response


def enable_api_key_auth(
    app: Any,
    api_keys: dict[str, str],
    allow_hashed: bool = False,
) -> None:
    """Enable API key authentication on the FastAPI app.

    Args:
        app: The FastAPI application.
        api_keys: Dict mapping key → client name.
        allow_hashed: If True, also check SHA-256 hashes of keys.
    """
    app.add_middleware(APIKeyAuthMiddleware, api_keys=api_keys, allow_hashed=allow_hashed)
