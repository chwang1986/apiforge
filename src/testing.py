"""ApiForge testing utilities.

Convenience helpers for testing ApiForge services without boilerplate.

Usage:
    from src.testing import make_forge, post_tool, get_tool

    f = make_forge(name="Test")

    @f.tool
    def add(a: int, b: int) -> int:
        # docstring: add two numbers
        return a + b

    result = post_tool(f, "add", {"a": 1, "b": 2})
    assert result == 3
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from fastapi.testclient import TestClient

from src.server import ApiForge


def make_forge(
    name: str = "Test",
    **kwargs: Any,
) -> ApiForge:
    """Create an ApiForge instance for testing.

    Args:
        name: Service name.
        **kwargs: Passed to ApiForge constructor.

    Returns:
        An ApiForge instance with TestClient accessible via .app.
    """
    return ApiForge(name=name, **kwargs)


def post_tool(
    forge: ApiForge,
    tool_name: str,
    payload: dict[str, Any] | None = None,
    *,
    headers: dict[str, str] | None = None,
    status_code: int = 200,
) -> Any:
    """POST to a tool endpoint and return the parsed JSON response.

    Args:
        forge: The ApiForge instance.
        tool_name: Name of the tool (e.g. "add" → /tools/add).
        payload: JSON body to send.
        headers: Extra headers.
        status_code: Expected HTTP status (asserted).

    Returns:
        The parsed JSON response body.
    """
    client = TestClient(forge.app)
    path = f"/tools/{tool_name}"
    resp = client.post(path, json=payload or {}, headers=headers or {})
    assert resp.status_code == status_code, (
        f"Expected {status_code}, got {resp.status_code}: {resp.text}"
    )
    return resp.json()


def get_tool(
    forge: ApiForge,
    tool_name: str,
    params: dict[str, Any] | None = None,
    *,
    headers: dict[str, str] | None = None,
    status_code: int = 200,
) -> Any:
    """GET a tool endpoint with query params.

    Args:
        forge: The ApiForge instance.
        tool_name: Name of the tool.
        params: Query string parameters.
        headers: Extra headers.
        status_code: Expected HTTP status.

    Returns:
        The parsed JSON response body.
    """
    client = TestClient(forge.app)
    path = f"/tools/{tool_name}"
    resp = client.get(path, params=params or {}, headers=headers or {})
    assert resp.status_code == status_code, (
        f"Expected {status_code}, got {resp.status_code}: {resp.text}"
    )
    return resp.json()


def assert_status(resp, expected: int) -> None:
    """Assert response status code."""
    assert resp.status_code == expected, (
        f"Expected {expected}, got {resp.status_code}: {resp.text[:200]}"
    )


def assert_json(resp, expected: Any) -> None:
    """Assert JSON body matches expected value."""
    actual = resp.json()
    assert actual == expected, f"Expected {expected!r}, got {actual!r}"


def assert_json_contains(resp: Any, key: str, value: Any = ...) -> None:
    """Assert JSON body contains a key (and optionally value)."""
    data = resp.json() if not isinstance(resp, dict) else resp
    assert key in data, f"Key {key!r} not in {list(data.keys())}"
    if value is not ...:
        assert data[key] == value, f"{key}: expected {value!r}, got {data[key]!r}"


def make_client(forge: ApiForge) -> TestClient:
    """Shorthand for creating a TestClient."""
    return TestClient(forge.app)


def raw_response(
    forge: ApiForge,
    method: str,
    path: str,
    *,
    json: Any = None,
    params: dict | None = None,
    files: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
) -> Any:
    """Send a raw request and return the response object.

    Use when you need to check headers, status, or raw text.
    """
    client = TestClient(forge.app)
    method = method.upper()
    if method == "GET":
        return client.get(path, params=params, headers=headers)
    elif method == "POST":
        if files:
            return client.post(path, files=files, data=data, headers=headers)
        return client.post(path, json=json, params=params, headers=headers)
    elif method == "PUT":
        return client.put(path, json=json, headers=headers)
    elif method == "DELETE":
        return client.delete(path, headers=headers)
    elif method == "PATCH":
        return client.patch(path, json=json, headers=headers)
    else:
        return client.request(method, path, json=json, headers=headers)


def fixture_forge(**kwargs: Any) -> ApiForge:
    """pytest fixture factory for ApiForge.

    Usage:
        @pytest.fixture
        def forge():
            return fixture_forge(name="Test")
    """
    return ApiForge(**kwargs)
