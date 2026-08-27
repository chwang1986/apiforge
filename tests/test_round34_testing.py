"""Round 34: Testing utilities tests."""

import pytest
from src.server import ApiForge
from src.testing import (
    make_forge,
    make_client,
    post_tool,
    get_tool,
    assert_status,
    assert_json,
    assert_json_contains,
    raw_response,
    fixture_forge,
)


def _build() -> ApiForge:
    f = make_forge(name="TestUtil")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    @f.tool(method="GET")
    def greet(name: str, punct: str = "!") -> str:
        """Greet."""
        return f"Hello, {name}{punct}"

    @f.tool
    def info() -> dict:
        """Info."""
        return {"ok": True, "count": 3}

    return f


# --- make_forge / make_client ---

def test_make_forge_returns_forge() -> None:
    f = make_forge(name="X")
    assert isinstance(f, ApiForge)
    assert f.name == "X"


def test_make_client() -> None:
    f = _build()
    c = make_client(f)
    assert c is not None
    assert c.get("/health").status_code == 200


# --- post_tool ---

def test_post_tool_returns_json() -> None:
    f = _build()
    result = post_tool(f, "add", {"a": 2, "b": 3})
    assert result == 5


def test_post_tool_wrong_status_raises() -> None:
    f = _build()
    with pytest.raises(AssertionError):
        post_tool(f, "add", {"a": 1, "b": 2}, status_code=500)


# --- get_tool ---

def test_get_tool_with_params() -> None:
    f = _build()
    result = get_tool(f, "greet", {"name": "World"})
    assert result == "Hello, World!"


def test_get_tool_defaults() -> None:
    f = _build()
    result = get_tool(f, "greet", {"name": "Bob", "punct": "?"})
    assert result == "Hello, Bob?"


# --- assert helpers ---

def test_assert_status_ok() -> None:
    f = _build()
    c = make_client(f)
    resp = c.get("/health")
    assert_status(resp, 200)


def test_assert_status_fail() -> None:
    f = _build()
    c = make_client(f)
    resp = c.get("/health")
    with pytest.raises(AssertionError):
        assert_status(resp, 404)


def test_assert_json_ok() -> None:
    f = _build()
    c = make_client(f)
    resp = c.post("/tools/add", json={"a": 1, "b": 1})
    assert_json(resp, 2)


def test_assert_json_fail() -> None:
    f = _build()
    c = make_client(f)
    resp = c.post("/tools/add", json={"a": 1, "b": 1})
    with pytest.raises(AssertionError):
        assert_json(resp, 999)


def test_assert_json_contains() -> None:
    f = _build()
    c = make_client(f)
    resp = c.post("/tools/info", json={})
    assert_json_contains(resp, "ok", True)
    assert_json_contains(resp, "count", 3)


def test_assert_json_contains_missing_key() -> None:
    f = _build()
    c = make_client(f)
    resp = c.post("/tools/info", json={})
    with pytest.raises(AssertionError):
        assert_json_contains(resp, "nonexistent")


# --- raw_response ---

def test_raw_response_post() -> None:
    f = _build()
    resp = raw_response(f, "POST", "/tools/add", json={"a": 4, "b": 5})
    assert resp.status_code == 200
    assert resp.json() == 9


def test_raw_response_get() -> None:
    f = _build()
    resp = raw_response(f, "GET", "/tools/greet", params={"name": "Z"})
    assert resp.status_code == 200


# --- fixture_forge ---

def test_fixture_forge() -> None:
    f = fixture_forge(name="Fixture")
    assert isinstance(f, ApiForge)
    assert f.name == "Fixture"
