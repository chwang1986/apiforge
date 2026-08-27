"""ApiForge middleware package.

Available middlewares:
- RequestLoggerMiddleware: request logging with timing
- enable_cors: CORS configuration
- RateLimitMiddleware: token bucket rate limiting
- APIKeyAuthMiddleware: API key authentication
"""

from src.middleware.auth import APIKeyAuthMiddleware, enable_api_key_auth, generate_api_key
from src.middleware.cors import enable_cors
from src.middleware.logging import RequestLoggerMiddleware, enable_request_logging
from src.middleware.rate_limit import RateLimitMiddleware, enable_rate_limiting
from src.middleware.request_id import RequestIDMiddleware, enable_request_id

__all__ = [
    "RequestLoggerMiddleware",
    "enable_request_logging",
    "enable_cors",
    "RateLimitMiddleware",
    "enable_rate_limiting",
    "APIKeyAuthMiddleware",
    "enable_api_key_auth",
    "generate_api_key",
    "RequestIDMiddleware",
    "enable_request_id",
]
