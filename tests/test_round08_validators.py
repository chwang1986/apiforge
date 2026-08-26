"""Round 8: Advanced parameter validation tests."""

import pytest
from fastapi.testclient import TestClient
from typing import Annotated

from src.server import ApiForge
from src.validators import (
    PositiveInt,
    PositiveFloat,
    LengthStr,
    RangeInt,
    RangeFloat,
    PatternStr,
    OneOf,
    EmailStr,
)


@pytest.fixture
def forge() -> ApiForge:
    """ApiForge with validated tool parameters."""
    f = ApiForge(name="ValidatorTest")

    @f.tool
    def create_user(
        name: LengthStr(2, 20),
        age: PositiveInt,
        email: EmailStr,
    ) -> dict:
        """Create a user with validated fields."""
        return {"name": name, "age": age, "email": email}

    @f.tool
    def set_port(
        port: RangeInt(1, 65535),
    ) -> str:
        """Set a valid port number."""
        return f"Port {port} configured"

    @f.tool
    def set_score(
        score: RangeFloat(0.0, 100.0),
    ) -> str:
        """Set a valid score."""
        return f"Score: {score}"

    @f.tool
    def set_code(
        code: PatternStr(r"^[A-Z]{3}-\d{4}$"),
    ) -> str:
        """Set an order code (e.g. ABC-1234)."""
        return f"Order {code} created"

    @f.tool
    def set_status(
        status: OneOf("active", "inactive", "suspended"),
    ) -> str:
        """Set account status."""
        return f"Status: {status}"

    return f


@pytest.fixture
def client(forge: ApiForge) -> TestClient:
    return TestClient(forge.app, raise_server_exceptions=False)


# --- LengthStr ---

def test_length_str_valid(client: TestClient) -> None:
    """Valid name within length range."""
    resp = client.post("/tools/create_user", json={
        "name": "Alice", "age": 30, "email": "alice@example.com"
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alice"


def test_length_str_too_short(client: TestClient) -> None:
    """Name too short → 422."""
    resp = client.post("/tools/create_user", json={
        "name": "A", "age": 30, "email": "a@example.com"
    })
    assert resp.status_code == 422


def test_length_str_too_long(client: TestClient) -> None:
    """Name too long → 422."""
    resp = client.post("/tools/create_user", json={
        "name": "x" * 25, "age": 30, "email": "a@example.com"
    })
    assert resp.status_code == 422


# --- PositiveInt ---

def test_positive_int_valid(client: TestClient) -> None:
    """Positive age passes."""
    resp = client.post("/tools/create_user", json={
        "name": "Bob", "age": 25, "email": "bob@example.com"
    })
    assert resp.status_code == 200


def test_positive_int_zero_fails(client: TestClient) -> None:
    """Zero age fails (must be > 0)."""
    resp = client.post("/tools/create_user", json={
        "name": "Bob", "age": 0, "email": "bob@example.com"
    })
    assert resp.status_code == 422


def test_positive_int_negative_fails(client: TestClient) -> None:
    """Negative age fails."""
    resp = client.post("/tools/create_user", json={
        "name": "Bob", "age": -5, "email": "bob@example.com"
    })
    assert resp.status_code == 422


# --- EmailStr ---

def test_email_valid(client: TestClient) -> None:
    """Valid email passes."""
    resp = client.post("/tools/create_user", json={
        "name": "Alice", "age": 30, "email": "alice@company.com"
    })
    assert resp.status_code == 200


def test_email_invalid(client: TestClient) -> None:
    """Invalid email → 422."""
    resp = client.post("/tools/create_user", json={
        "name": "Alice", "age": 30, "email": "not-an-email"
    })
    assert resp.status_code == 422


# --- RangeInt ---

def test_range_int_valid(client: TestClient) -> None:
    """Port 8080 is valid."""
    resp = client.post("/tools/set_port", json={"port": 8080})
    assert resp.status_code == 200
    assert resp.json() == "Port 8080 configured"


def test_range_int_too_low(client: TestClient) -> None:
    """Port 0 is invalid."""
    resp = client.post("/tools/set_port", json={"port": 0})
    assert resp.status_code == 422


def test_range_int_too_high(client: TestClient) -> None:
    """Port 99999 is invalid."""
    resp = client.post("/tools/set_port", json={"port": 99999})
    assert resp.status_code == 422


# --- RangeFloat ---

def test_range_float_valid(client: TestClient) -> None:
    """Score 75.5 is valid."""
    resp = client.post("/tools/set_score", json={"score": 75.5})
    assert resp.status_code == 200


def test_range_float_out_of_range(client: TestClient) -> None:
    """Score 150 is invalid."""
    resp = client.post("/tools/set_score", json={"score": 150.0})
    assert resp.status_code == 422


# --- PatternStr ---

def test_pattern_valid(client: TestClient) -> None:
    """Valid code ABC-1234 passes."""
    resp = client.post("/tools/set_code", json={"code": "ABC-1234"})
    assert resp.status_code == 200
    assert resp.json() == "Order ABC-1234 created"


def test_pattern_invalid(client: TestClient) -> None:
    """Invalid code abc-1234 fails (lowercase)."""
    resp = client.post("/tools/set_code", json={"code": "abc-1234"})
    assert resp.status_code == 422


def test_pattern_wrong_format(client: TestClient) -> None:
    """Wrong format 123-ABC fails."""
    resp = client.post("/tools/set_code", json={"code": "123-ABC"})
    assert resp.status_code == 422


# --- OneOf ---

def test_oneof_valid(client: TestClient) -> None:
    """'active' is a valid status."""
    resp = client.post("/tools/set_status", json={"status": "active"})
    assert resp.status_code == 200
    assert resp.json() == "Status: active"


def test_oneof_invalid(client: TestClient) -> None:
    """'unknown' is not a valid status."""
    resp = client.post("/tools/set_status", json={"status": "unknown"})
    assert resp.status_code == 422
