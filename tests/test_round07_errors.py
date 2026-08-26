"""Round 7: Unified error response format tests."""

import pytest
from fastapi.testclient import TestClient

from src.errors import ToolError, ValidationError
from src.server import ApiForge


@pytest.fixture
def forge() -> ApiForge:
    """ApiForge with error-raising tools."""
    f = ApiForge(name="ErrorTest")

    @f.tool
    def divide(a: float, b: float) -> float:
        """Divide a by b."""
        if b == 0:
            raise ToolError("Division by zero not allowed", code="DIVISION_BY_ZERO", status_code=400)
        return a / b

    @f.tool
    def validate_age(age: int) -> str:
        """Validate age is in range."""
        if age < 0 or age > 150:
            raise ValidationError("Age must be between 0 and 150", field="age")
        return f"Valid age: {age}"

    @f.tool
    def crash() -> str:
        """Always crashes."""
        raise RuntimeError("unexpected crash")

    return f


@pytest.fixture
def client(forge: ApiForge) -> TestClient:
    return TestClient(forge.app, raise_server_exceptions=False)


# --- ToolError with custom code/status ---

def test_tool_error_custom_code(client: TestClient) -> None:
    """ToolError produces structured error with custom code."""
    resp = client.post("/tools/divide", json={"a": 10, "b": 0})
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "DIVISION_BY_ZERO"
    assert data["error"]["message"] == "Division by zero not allowed"
    assert data["error"]["tool"] == "divide"


def test_tool_error_default(client: TestClient) -> None:
    """Generic RuntimeError produces INTERNAL_ERROR code."""
    resp = client.post("/tools/crash", json={})
    assert resp.status_code == 500
    data = resp.json()
    assert data["error"]["code"] == "INTERNAL_ERROR"
    assert "unexpected crash" in data["error"]["message"]


# --- ValidationError ---

def test_validation_error(client: TestClient) -> None:
    """ValidationError produces 422 with field info."""
    resp = client.post("/tools/validate_age", json={"age": -5})
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "VALIDATION_FAILED"
    assert "age" in data["error"]["message"].lower()


def test_validation_error_valid(client: TestClient) -> None:
    """Valid age returns success."""
    resp = client.post("/tools/validate_age", json={"age": 25})
    assert resp.status_code == 200
    assert resp.json() == "Valid age: 25"


# --- 404 error format ---

def test_404_has_error_structure(client: TestClient) -> None:
    """Unknown endpoints return structured 404 error."""
    resp = client.post("/tools/nonexistent", json={})
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


# --- Method not allowed ---

def test_method_not_allowed(client: TestClient) -> None:
    """GET on a POST endpoint returns structured error."""
    resp = client.get("/tools/divide")
    assert resp.status_code == 405
    data = resp.json()
    assert "error" in data


# --- Envelope consistency ---

def test_error_always_has_envelope(client: TestClient) -> None:
    """All error responses use the {error: {...}} envelope."""
    cases = [
        (client.post, "/tools/divide", {"a": 1, "b": 0}, 400),
        (client.post, "/tools/crash", {}, 500),
        (client.post, "/tools/nope", {}, 404),
    ]
    for method, path, body, expected_status in cases:
        resp = method(path, json=body)
        assert resp.status_code == expected_status
        data = resp.json()
        assert "error" in data, f"Missing error envelope on {path}"
        assert "code" in data["error"]
        assert "message" in data["error"]
