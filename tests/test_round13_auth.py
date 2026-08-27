"""Round 13: API Key authentication tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.middleware.auth import generate_api_key, hash_api_key


VALID_KEY = "aforge_test123456789"
CLIENT_NAME = "test-client"


@pytest.fixture
def forge_auth() -> ApiForge:
    """ApiForge with API key auth enabled."""
    f = ApiForge(
        name="Auth Test",
        api_keys={VALID_KEY: CLIENT_NAME},
    )

    @f.tool
    def secret() -> str:
        """Return secret data."""
        return "top secret"

    return f


@pytest.fixture
def client(forge_auth: ApiForge) -> TestClient:
    return TestClient(forge_auth.app, raise_server_exceptions=False)


# --- Key generation ---

def test_generate_api_key_format() -> None:
    """Generated key has correct prefix and length."""
    key = generate_api_key()
    assert key.startswith("aforge_")
    assert len(key) == len("aforge_") + 32  # 16 bytes = 32 hex chars


def test_generate_api_key_unique() -> None:
    """Two generated keys are different."""
    k1 = generate_api_key()
    k2 = generate_api_key()
    assert k1 != k2


def test_hash_api_key_deterministic() -> None:
    """Same key always produces same hash."""
    h1 = hash_api_key("test")
    h2 = hash_api_key("test")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


# --- Auth: no key ---

def test_no_key_returns_401(client: TestClient) -> None:
    """Request without API key returns 401."""
    resp = client.post("/tools/secret", json={})
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "AUTH_MISSING"


# --- Auth: invalid key ---

def test_invalid_key_returns_401(client: TestClient) -> None:
    """Request with wrong key returns 401."""
    resp = client.post(
        "/tools/secret",
        json={},
        headers={"Authorization": "Bearer wrong_key_here"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "AUTH_INVALID"


# --- Auth: valid key via Bearer ---

def test_valid_bearer_key(client: TestClient) -> None:
    """Request with valid Bearer token succeeds."""
    resp = client.post(
        "/tools/secret",
        json={},
        headers={"Authorization": f"Bearer {VALID_KEY}"},
    )
    assert resp.status_code == 200
    assert resp.json() == "top secret"


# --- Auth: valid key via X-API-Key ---

def test_valid_x_api_key_header() -> None:
    """Request with X-API-Key header succeeds."""
    f = ApiForge(name="XKey", api_keys={VALID_KEY: "xclient"})

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={}, headers={"X-API-Key": VALID_KEY})
    assert resp.status_code == 200
    assert resp.json() == "pong"


# --- Auth: client name header ---

def test_authenticated_client_header(client: TestClient) -> None:
    """Successful response includes X-Authenticated-Client header."""
    resp = client.post(
        "/tools/secret",
        json={},
        headers={"Authorization": f"Bearer {VALID_KEY}"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-authenticated-client") == CLIENT_NAME


# --- Auth: public paths are exempt ---

def test_health_exempt(client: TestClient) -> None:
    """Health check works without auth."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_docs_exempt(client: TestClient) -> None:
    """Swagger docs accessible without auth."""
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200


# --- Auth: 401 has WWW-Authenticate header ---

def test_401_has_www_authenticate(client: TestClient) -> None:
    """401 response includes WWW-Authenticate header."""
    resp = client.post("/tools/secret", json={})
    assert resp.status_code == 401
    assert "www-authenticate" in resp.headers
    assert "Bearer" in resp.headers["www-authenticate"]


# --- No auth (default) ---

def test_no_auth_by_default() -> None:
    """Without api_keys, requests work without auth header."""
    f = ApiForge(name="NoAuth")

    @f.tool
    def hello() -> str:
        """Say hi."""
        return "hi"

    c = TestClient(f.app)
    resp = c.post("/tools/hello", json={})
    assert resp.status_code == 200
    assert resp.json() == "hi"
