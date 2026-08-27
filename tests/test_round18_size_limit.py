"""Round 18: Payload size limit tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.middleware.size_limit import SizeLimitMiddleware, enable_size_limit, DEFAULT_MAX_BYTES


def make_forgery(max_bytes: int | None = None) -> tuple[ApiForge, TestClient]:
    """Helper to create a forge with size limit."""
    f = ApiForge(name="SizeTest")

    @f.tool
    def receive(data: str) -> str:
        """Echo back data."""
        return f"received {len(data)} chars"

    if max_bytes is not None:
        f.app.add_middleware(SizeLimitMiddleware, max_bytes=max_bytes)

    c = TestClient(f.app, raise_server_exceptions=False)
    return f, c


# --- Small payload passes ---

def test_small_payload_passes() -> None:
    """Normal small payload is accepted."""
    f = ApiForge(name="Small")

    @f.tool
    def echo(msg: str) -> str:
        """Echo."""
        return msg

    f.app.add_middleware(SizeLimitMiddleware, max_bytes=1024)  # 1 KB limit
    c = TestClient(f.app)

    resp = c.post("/tools/echo", json={"msg": "hello"})
    assert resp.status_code == 200
    assert resp.json() == "hello"


# --- Oversized payload rejected ---

def test_oversized_payload_rejected() -> None:
    """Payload exceeding limit returns 413."""
    f = ApiForge(name="Big")

    @f.tool
    def echo(msg: str) -> str:
        """Echo."""
        return msg

    f.app.add_middleware(SizeLimitMiddleware, max_bytes=10)  # 10 byte limit
    c = TestClient(f.app, raise_server_exceptions=False)

    # Send a payload that will exceed 10 bytes
    resp = c.post("/tools/echo", json={"msg": "this is definitely more than 10 bytes"})
    assert resp.status_code == 413
    data = resp.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "too large" in data["error"]["message"].lower()


# --- Boundary: exactly at limit ---

def test_boundary_payload() -> None:
    """Payload exactly at limit is allowed."""
    f = ApiForge(name="Boundary")

    @f.tool
    def ping() -> str:
        """Ping."""
        return "pong"

    # {"json"} = 6 bytes body, set limit to 6
    f.app.add_middleware(SizeLimitMiddleware, max_bytes=6)
    c = TestClient(f.app, raise_server_exceptions=False)

    resp = c.post("/tools/ping", json={})
    # Should be allowed (6 bytes <= 6 bytes limit)
    assert resp.status_code == 200


# --- Default limit is 1MB ---

def test_default_max_bytes() -> None:
    """Default is 1 MB."""
    assert DEFAULT_MAX_BYTES == 1_048_576


# --- GET requests (no body) always pass ---

def test_get_request_passes() -> None:
    """GET requests have no body, always pass."""
    f = ApiForge(name="GET")

    @f.tool
    def ping() -> str:
        """Ping."""
        return "pong"

    f.app.add_middleware(SizeLimitMiddleware, max_bytes=1)  # tiny limit
    c = TestClient(f.app)

    # GET to health (no body)
    resp = c.get("/health")
    assert resp.status_code == 200


# --- No size limit by default ---

def test_no_limit_by_default() -> None:
    """Without size_limit middleware, no 413 responses."""
    f = ApiForge(name="NoLimit")

    @f.tool
    def echo(msg: str) -> str:
        """Echo."""
        return msg

    c = TestClient(f.app)
    # Large payload should be fine (no middleware)
    resp = c.post("/tools/echo", json={"msg": "x" * 10000})
    assert resp.status_code == 200


# --- enable_size_limit helper ---

def test_enable_size_limit_helper() -> None:
    """enable_size_limit() function works."""
    f = ApiForge(name="Helper")

    @f.tool
    def echo(msg: str) -> str:
        """Echo."""
        return msg

    enable_size_limit(f.app, max_bytes=5)
    c = TestClient(f.app, raise_server_exceptions=False)

    resp = c.post("/tools/echo", json={"msg": "way too long"})
    assert resp.status_code == 413
