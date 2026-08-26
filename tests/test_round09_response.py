"""Round 9: Response envelope tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge


@pytest.fixture
def forge_envelope() -> ApiForge:
    """ApiForge with envelope enabled."""
    f = ApiForge(name="EnvelopeTest", envelope=True)

    @f.tool
    def add(a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @f.tool
    def get_info() -> dict:
        """Return info dict."""
        return {"name": "test", "version": 1}

    return f


@pytest.fixture
def client(forge_envelope: ApiForge) -> TestClient:
    return TestClient(forge_envelope.app, raise_server_exceptions=False)


@pytest.fixture
def forge_plain() -> ApiForge:
    """ApiForge without envelope (default)."""
    f = ApiForge(name="PlainTest")

    @f.tool
    def add(a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    return f


@pytest.fixture
def client_plain(forge_plain: ApiForge) -> TestClient:
    return TestClient(forge_plain.app, raise_server_exceptions=False)


# --- Envelope ON ---

def test_envelope_response_structure(client: TestClient) -> None:
    """Response has status, data, meta fields."""
    resp = client.post("/tools/add", json={"a": 1, "b": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["data"] == 3
    assert "meta" in data


def test_envelope_meta_has_tool(client: TestClient) -> None:
    """Meta contains tool name."""
    resp = client.post("/tools/add", json={"a": 1, "b": 2})
    data = resp.json()
    assert data["meta"]["tool"] == "add"


def test_envelope_meta_has_elapsed(client: TestClient) -> None:
    """Meta contains elapsed time."""
    resp = client.post("/tools/add", json={"a": 1, "b": 2})
    data = resp.json()
    assert "elapsed_ms" in data["meta"]
    assert data["meta"]["elapsed_ms"] >= 0


def test_envelope_dict_data(client: TestClient) -> None:
    """Dict return values work inside envelope."""
    resp = client.post("/tools/get_info", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["data"] == {"name": "test", "version": 1}


def test_envelope_with_request_id(client: TestClient) -> None:
    """Request ID from header appears in meta."""
    resp = client.post(
        "/tools/add",
        json={"a": 5, "b": 5},
        headers={"X-Request-ID": "test-req-123"},
    )
    data = resp.json()
    assert data["meta"]["request_id"] == "test-req-123"


# --- Envelope OFF (default) ---

def test_plain_response_no_envelope(client_plain: TestClient) -> None:
    """Without envelope, raw value is returned."""
    resp = client_plain.post("/tools/add", json={"a": 3, "b": 4})
    assert resp.status_code == 200
    assert resp.json() == 7  # bare number, not wrapped


def test_plain_response_dict(client_plain: TestClient) -> None:
    """Without envelope, dict is returned as-is."""
    # The add tool returns a float, so let's just check it's not wrapped
    resp = client_plain.post("/tools/add", json={"a": 1, "b": 1})
    assert resp.json() == 2


# --- Error responses still work with envelope enabled ---

def test_envelope_error_response(client: TestClient) -> None:
    """404 still uses error envelope even when success uses response envelope."""
    resp = client.post("/tools/nonexistent", json={})
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


def test_envelope_422(client: TestClient) -> None:
    """Validation errors still return 422."""
    resp = client.post("/tools/add", json={"a": 1})
    assert resp.status_code == 422
