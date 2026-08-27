"""Round 28: Namespace (grouping) tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.namespace import Namespace


# --- Namespace basics ---

def test_namespace_tool() -> None:
    """Tool in a namespace gets prefixed path."""
    f = ApiForge(name="NS")
    users = f.namespace("users")

    @users.tool
    def greet(name: str) -> str:
        """Greet."""
        return f"Hello, {name}!"

    c = TestClient(f.app)
    resp = c.post("/users/greet", json={"name": "Bob"})
    assert resp.status_code == 200
    assert resp.json() == "Hello, Bob!"


def test_namespace_with_get() -> None:
    """Namespace supports GET method tools."""
    f = ApiForge(name="NS GET")
    items = f.namespace("items")

    @items.tool(method="GET")
    def list_all() -> list:
        """List items."""
        return ["a", "b"]

    c = TestClient(f.app)
    resp = c.get("/items/list_all")
    assert resp.status_code == 200
    assert resp.json() == ["a", "b"]


def test_nested_namespaces() -> None:
    """Nested namespaces stack prefixes."""
    f = ApiForge(name="Nested")
    admin = f.namespace("admin")
    audit = admin.namespace("audit")

    @audit.tool
    def logs() -> list:
        """Audit logs."""
        return ["login", "logout"]

    c = TestClient(f.app)
    resp = c.post("/admin/audit/logs", json={})
    assert resp.status_code == 200
    assert resp.json() == ["login", "logout"]


def test_namespace_full_prefix() -> None:
    """Namespace._full_prefix computes chain."""
    f = ApiForge(name="Prefix")
    admin = f.namespace("admin")
    audit = admin.namespace("audit")
    assert admin._full_prefix() == "admin"
    assert audit._full_prefix() == "admin/audit"


def test_namespace_full_path() -> None:
    """Namespace.full_path builds route."""
    f = ApiForge(name="Path")
    users = f.namespace("users")
    assert users.full_path("get") == "/users/get"


def test_namespace_tag_in_openapi() -> None:
    """Namespace tools appear under their tag in OpenAPI."""
    f = ApiForge(name="Tags")
    users = f.namespace("users")

    @users.tool
    def get(id: int) -> dict:
        """Get user."""
        return {"id": id}

    c = TestClient(f.app)
    spec = c.get("/api/openapi.json").json()
    paths = spec["paths"]
    assert "/users/get" in paths
    # Tag should be "users"
    op = paths["/users/get"]["post"]
    assert "users" in op.get("tags", [])


def test_namespace_coexists_with_forge_tools() -> None:
    """Namespace tools and root forge tools coexist."""
    f = ApiForge(name="Mixed")

    @f.tool
    def root_tool() -> str:
        """Root."""
        return "root"

    users = f.namespace("users")

    @users.tool
    def user_tool() -> str:
        """User."""
        return "user"

    c = TestClient(f.app)
    assert c.post("/tools/root_tool", json={}).json() == "root"
    assert c.post("/users/user_tool", json={}).json() == "user"
