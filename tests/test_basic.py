"""Basic tests for ApiForge core functionality."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge


@pytest.fixture
def forge() -> ApiForge:
    """Create an ApiForge instance with sample tools registered."""
    f = ApiForge(name="TestService")

    @f.tool
    def echo(message: str) -> str:
        """Echo the input message back."""
        return message

    @f.tool
    def add(a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @f.tool
    def reverse(text: str) -> str:
        """Reverse a string."""
        return text[::-1]

    return f


@pytest.fixture
def client(forge: ApiForge) -> TestClient:
    """Create a test client from the forge instance."""
    return TestClient(forge.app)


# --- Health ---

def test_health(client: TestClient) -> None:
    """Test the health check endpoint."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "TestService"
    assert data["version"]


# --- Tools ---

def test_echo(client: TestClient) -> None:
    """Test the echo tool."""
    resp = client.post("/tools/echo", json={"message": "hello"})
    assert resp.status_code == 200
    assert resp.json() == "hello"


def test_add(client: TestClient) -> None:
    """Test the add tool."""
    resp = client.post("/tools/add", json={"a": 3, "b": 4})
    assert resp.status_code == 200
    assert resp.json() == 7


def test_add_negative(client: TestClient) -> None:
    """Test the add tool with negative numbers."""
    resp = client.post("/tools/add", json={"a": -1, "b": 5})
    assert resp.status_code == 200
    assert resp.json() == 4


def test_reverse(client: TestClient) -> None:
    """Test the reverse tool."""
    resp = client.post("/tools/reverse", json={"text": "abcdef"})
    assert resp.status_code == 200
    assert resp.json() == "fedcba"


def test_missing_param_returns_422(client: TestClient) -> None:
    """Test that missing required params return 422."""
    resp = client.post("/tools/add", json={"a": 1})
    assert resp.status_code == 422


# --- OpenAPI ---

def test_openapi_available(client: TestClient) -> None:
    """Test that OpenAPI docs are accessible."""
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["info"]["title"] == "TestService"
    assert "/tools/echo" in data["paths"]
    assert "/tools/add" in data["paths"]
    assert "/tools/reverse" in data["paths"]


def test_openapi_has_tool_descriptions(client: TestClient) -> None:
    """Test that tools have docstring descriptions in OpenAPI."""
    resp = client.get("/api/openapi.json")
    data = resp.json()
    echo_op = data["paths"]["/tools/echo"]["post"]
    assert echo_op["summary"] == "Echo"
    assert "Echo" in echo_op["description"]
