"""Round 21: GET request support tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge


# --- Basic GET with no params ---

def test_get_no_params() -> None:
    """GET tool with no parameters works."""
    f = ApiForge(name="GET Basic")

    @f.tool(method="GET")
    def time() -> str:
        """Return current time string."""
        return "12:00:00"

    c = TestClient(f.app)
    resp = c.get("/tools/time")
    assert resp.status_code == 200
    assert resp.json() == "12:00:00"


# --- GET with required query params ---

def test_get_with_required_params() -> None:
    """GET tool with required params from query string."""
    f = ApiForge(name="GET Params")

    @f.tool(method="GET")
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    c = TestClient(f.app)
    resp = c.get("/tools/add", params={"a": 3, "b": 7})
    assert resp.status_code == 200
    assert resp.json() == 10


# --- GET with optional params (defaults) ---

def test_get_with_defaults() -> None:
    """GET tool with default parameter values."""
    f = ApiForge(name="GET Defaults")

    @f.tool(method="GET")
    def search(query: str, limit: int = 5) -> dict:
        """Search with limit."""
        return {"query": query, "limit": limit}

    c = TestClient(f.app)

    # Use default limit
    resp = c.get("/tools/search", params={"query": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "hello"
    assert data["limit"] == 5

    # Override limit
    resp = c.get("/tools/search", params={"query": "hello", "limit": 20})
    assert resp.json()["limit"] == 20


# --- GET type coercion ---

def test_get_int_coercion() -> None:
    """Query string int is coerced correctly."""
    f = ApiForge(name="GET Int")

    @f.tool(method="GET")
    def multiply(a: int, b: int) -> int:
        """Multiply."""
        return a * b

    c = TestClient(f.app)
    resp = c.get("/tools/multiply", params={"a": "4", "b": "5"})
    assert resp.json() == 20


def test_get_float_coercion() -> None:
    """Query string float is coerced correctly."""
    f = ApiForge(name="GET Float")

    @f.tool(method="GET")
    def scale(value: float, factor: float = 2.0) -> float:
        """Scale a value."""
        return value * factor

    c = TestClient(f.app)
    resp = c.get("/tools/scale", params={"value": "3.5"})
    assert resp.json() == 7.0


def test_get_bool_coercion() -> None:
    """Query string bool is coerced correctly."""
    f = ApiForge(name="GET Bool")

    @f.tool(method="GET")
    def toggle(flag: bool = False) -> str:
        """Toggle flag."""
        return "on" if flag else "off"

    c = TestClient(f.app)
    assert c.get("/tools/toggle").json() == "off"
    assert c.get("/tools/toggle", params={"flag": "true"}).json() == "on"


# --- Missing required param → 422 ---

def test_get_missing_required_param() -> None:
    """Missing required query param returns 422."""
    f = ApiForge(name="GET Missing")

    @f.tool(method="GET")
    def greet(name: str) -> str:
        """Greet by name."""
        return f"Hello, {name}!"

    c = TestClient(f.app, raise_server_exceptions=False)
    resp = c.get("/tools/greet")
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "VALIDATION_FAILED"


# --- POST still works (backward compat) ---

def test_post_still_default() -> None:
    """Without method param, tool is POST (backward compat)."""
    f = ApiForge(name="POST Compat")

    @f.tool
    def echo(msg: str) -> str:
        """Echo."""
        return msg

    c = TestClient(f.app)
    # POST works
    resp = c.post("/tools/echo", json={"msg": "hi"})
    assert resp.status_code == 200
    # GET should NOT work (405)
    resp = c.get("/tools/echo")
    assert resp.status_code == 405


# --- GET with async tool ---

def test_get_async_tool() -> None:
    """GET works with async tool functions."""
    f = ApiForge(name="GET Async")

    @f.tool(method="GET")
    async def fetch(url: str) -> str:
        """Fetch a URL (simulated)."""
        return f"content of {url}"

    c = TestClient(f.app)
    resp = c.get("/tools/fetch", params={"url": "https://example.com"})
    assert resp.status_code == 200
    assert resp.json() == "content of https://example.com"


# --- GET with envelope ---

def test_get_with_envelope() -> None:
    """GET works with response envelope."""
    f = ApiForge(name="GET Env", envelope=True)

    @f.tool(method="GET")
    def ping() -> str:
        """Ping."""
        return "pong"

    c = TestClient(f.app)
    resp = c.get("/tools/ping")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["data"] == "pong"
    assert data["meta"]["tool"] == "ping"


# --- Mixed GET and POST tools ---

def test_mixed_get_and_post() -> None:
    """Same forge can have both GET and POST tools."""
    f = ApiForge(name="Mixed")

    @f.tool
    def create(name: str) -> str:
        """Create resource (POST)."""
        return f"created: {name}"

    @f.tool(method="GET")
    def list_items() -> list:
        """List items (GET)."""
        return ["a", "b", "c"]

    c = TestClient(f.app)

    # POST works
    resp = c.post("/tools/create", json={"name": "x"})
    assert resp.status_code == 200
    assert resp.json() == "created: x"

    # GET works
    resp = c.get("/tools/list_items")
    assert resp.status_code == 200
    assert resp.json() == ["a", "b", "c"]
