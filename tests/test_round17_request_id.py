"""Round 17: Request ID / Correlation ID tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.middleware.request_id import generate_request_id


# --- generate_request_id ---

def test_generate_request_id_format() -> None:
    """Generated ID is 12 hex chars."""
    rid = generate_request_id()
    assert len(rid) == 12
    assert all(c in "0123456789abcdef" for c in rid)


def test_generate_request_id_unique() -> None:
    """Two generated IDs are different."""
    r1 = generate_request_id()
    r2 = generate_request_id()
    assert r1 != r2


# --- Integration: auto-generated ---

def test_response_has_request_id_header() -> None:
    """Every response includes X-Request-ID header."""
    f = ApiForge(name="RID Test")

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    rid = resp.headers["x-request-id"]
    assert len(rid) == 12


def test_different_requests_get_different_ids() -> None:
    """Each request gets a unique ID."""
    f = ApiForge(name="RID Unique")

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    r1 = c.post("/tools/ping", json={})
    r2 = c.post("/tools/ping", json={})
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


# --- Integration: client-provided ID preserved ---

def test_client_request_id_preserved() -> None:
    """If client sends X-Request-ID, it's echoed back."""
    f = ApiForge(name="RID Preserve")

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post(
        "/tools/ping",
        json={},
        headers={"X-Request-ID": "my-custom-trace-id-123"},
    )
    assert resp.status_code == 200
    assert resp.headers["x-request-id"] == "my-custom-trace-id-123"


# --- Request ID in error responses ---

def test_error_response_includes_request_id() -> None:
    """404 error response includes X-Request-ID."""
    f = ApiForge(name="RID Error")

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app, raise_server_exceptions=False)
    resp = c.post("/tools/nonexistent", json={})
    assert resp.status_code == 404
    assert "x-request-id" in resp.headers


def test_tool_error_includes_request_id() -> None:
    """500 tool error includes request_id in body."""
    from src.errors import ToolError

    f = ApiForge(name="RID ToolError")

    @f.tool
    def fail() -> str:
        """Always fails."""
        raise ToolError("Something broke", code="TEST_ERROR")

    c = TestClient(f.app, raise_server_exceptions=False)
    resp = c.post(
        "/tools/fail",
        json={},
        headers={"X-Request-ID": "trace-abc-456"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["request_id"] == "trace-abc-456"


# --- Health endpoint also gets ID ---

def test_health_has_request_id() -> None:
    """Health endpoint response includes X-Request-ID."""
    f = ApiForge(name="RID Health")
    c = TestClient(f.app)
    resp = c.get("/health")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers


# --- Request ID doesn't break other middleware ---

def test_request_id_with_logging() -> None:
    """Request ID works alongside logging middleware."""
    f = ApiForge(name="RID Log", log_requests=True)

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert "x-response-time" in resp.headers


def test_request_id_with_rate_limit() -> None:
    """Request ID works alongside rate limiting."""
    f = ApiForge(name="RID RL", rate_limit={"requests": 10, "window_seconds": 60})

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert "x-ratelimit-limit" in resp.headers
