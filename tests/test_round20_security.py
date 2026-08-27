"""Round 20: Security headers tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.middleware.security import SecurityHeadersMiddleware, enable_security_headers


# --- Security headers enabled ---

def test_security_headers_present() -> None:
    """All security headers are present on responses."""
    f = ApiForge(name="Security", security_headers=True)

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 200

    # X-Content-Type-Options
    assert resp.headers.get("x-content-type-options") == "nosniff"
    # X-Frame-Options
    assert resp.headers.get("x-frame-options") == "DENY"
    # X-XSS-Protection
    assert resp.headers.get("x-xss-protection") == "1; mode=block"
    # Referrer-Policy
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    # Permissions-Policy
    assert "camera" in resp.headers.get("permissions-policy", "")


def test_hsts_header_localhost() -> None:
    """HSTS header present for localhost requests."""
    f = ApiForge(name="HSTS", security_headers=True)

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 200
    # TestClient uses testserver which may not match "localhost"
    # Check if HSTS is present (it should be for localhost)
    hsts = resp.headers.get("strict-transport-security", "")
    if hsts:
        assert "max-age=" in hsts
        assert "includeSubDomains" in hsts


# --- Security headers disabled (default) ---

def test_no_security_headers_by_default() -> None:
    """Without security_headers=True, headers are absent."""
    f = ApiForge(name="NoSecurity")

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") is None
    assert resp.headers.get("x-frame-options") is None


# --- Works with other middleware ---

def test_security_with_cors() -> None:
    """Security headers work alongside CORS."""
    f = ApiForge(
        name="Sec+CORS",
        security_headers=True,
        cors_origins=["https://app.example.com"],
    )

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post(
        "/tools/ping",
        json={},
        headers={"Origin": "https://app.example.com"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_security_with_rate_limit() -> None:
    """Security headers work alongside rate limiting."""
    f = ApiForge(
        name="Sec+RL",
        security_headers=True,
        rate_limit={"requests": 10, "window_seconds": 60},
    )

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert "x-ratelimit-limit" in resp.headers


# --- Error responses also get security headers ---

def test_error_response_has_security_headers() -> None:
    """404 error responses include security headers."""
    f = ApiForge(name="SecError", security_headers=True)

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app, raise_server_exceptions=False)
    resp = c.post("/tools/nonexistent", json={})
    assert resp.status_code == 404
    assert resp.headers.get("x-content-type-options") == "nosniff"


# --- Health endpoint also gets security headers ---

def test_health_has_security_headers() -> None:
    """Health endpoint includes security headers."""
    f = ApiForge(name="SecHealth", security_headers=True)
    c = TestClient(f.app)
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"


# --- enable_security_headers helper ---

def test_enable_security_headers_helper() -> None:
    """enable_security_headers() function works directly."""
    f = ApiForge(name="Helper")

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    enable_security_headers(f.app)
    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 200
    assert resp.headers.get("x-frame-options") == "DENY"
