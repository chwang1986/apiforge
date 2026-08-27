"""Round 11: CORS middleware tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge


@pytest.fixture
def forge_cors() -> ApiForge:
    """ApiForge with CORS enabled for specific origins."""
    f = ApiForge(
        name="CORS Test",
        cors_origins=["https://app.example.com", "https://admin.example.com"],
    )

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    return f


@pytest.fixture
def forge_wildcard() -> ApiForge:
    """ApiForge with wildcard CORS."""
    f = ApiForge(name="Wildcard CORS", cors_origins=["*"])

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    return f


@pytest.fixture
def client(forge_cors: ApiForge) -> TestClient:
    return TestClient(forge_cors.app, raise_server_exceptions=False)


# --- CORS enabled: allowed origin ---

def test_cors_allowed_origin(client: TestClient) -> None:
    """Request from allowed origin gets CORS headers."""
    resp = client.post(
        "/tools/ping",
        json={},
        headers={"Origin": "https://app.example.com"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"


def test_cors_preflight_request(client: TestClient) -> None:
    """OPTIONS preflight returns 200 with CORS headers."""
    resp = client.options(
        "/tools/ping",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"
    assert "access-control-allow-methods" in resp.headers


def test_cors_allowed_methods(client: TestClient) -> None:
    """Preflight response includes allowed methods."""
    resp = client.options(
        "/tools/ping",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "POST" in resp.headers.get("access-control-allow-methods", "")


# --- CORS: disallowed origin ---

def test_cors_disallowed_origin(client: TestClient) -> None:
    """Request from disallowed origin does NOT get allow-origin header."""
    resp = client.post(
        "/tools/ping",
        json={},
        headers={"Origin": "https://evil.example.com"},
    )
    # The request itself may still succeed (CORS is enforced by browser)
    # But the allow-origin header should NOT be set
    assert resp.headers.get("access-control-allow-origin") is None


# --- Wildcard CORS ---

def test_wildcard_cors() -> None:
    """Wildcard origin: when allow_credentials=True, origin is echoed back."""
    f = ApiForge(name="WC", cors_origins=["*"])

    @f.tool
    def hello() -> str:
        """Say hi."""
        return "hi"

    c = TestClient(f.app)
    resp = c.post("/tools/hello", json={}, headers={"Origin": "https://anything.com"})
    # With allow_credentials=True (default), CORS echoes the origin instead of *
    assert resp.headers.get("access-control-allow-origin") == "https://anything.com"


# --- No CORS (default) ---

def test_no_cors_by_default() -> None:
    """Without cors_origins, no CORS headers are present."""
    f = ApiForge(name="NoCORS")

    @f.tool
    def hello() -> str:
        """Say hi."""
        return "hi"

    c = TestClient(f.app)
    resp = c.post("/tools/hello", json={}, headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in resp.headers


# --- CORS doesn't break existing functionality ---

def test_cors_normal_request_still_works(client: TestClient) -> None:
    """Normal POST without Origin header still works fine."""
    resp = client.post("/tools/ping", json={})
    assert resp.status_code == 200
    assert resp.json() == "pong"
