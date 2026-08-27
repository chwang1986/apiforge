"""Round 22: Path parameters tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src._internal import extract_path_params, build_body_model


# --- extract_path_params ---

def test_extract_path_params_single() -> None:
    assert extract_path_params("/tools/users/{user_id}") == ["user_id"]


def test_extract_path_params_multiple() -> None:
    assert extract_path_params("/tools/users/{uid}/posts/{pid}") == ["uid", "pid"]


def test_extract_path_params_none() -> None:
    assert extract_path_params("/tools/simple") == []


# --- GET with single path param ---

def test_get_single_path_param() -> None:
    """GET /tools/users/{user_id} with int path param."""
    f = ApiForge(name="PathParam")

    @f.tool(method="GET", path="/tools/users/{user_id}")
    def get_user(user_id: int) -> dict:
        """Get user by ID."""
        return {"id": user_id, "name": f"user_{user_id}"}

    c = TestClient(f.app)
    resp = c.get("/tools/users/42")
    assert resp.status_code == 200
    assert resp.json() == {"id": 42, "name": "user_42"}


# --- GET with multiple path params ---

def test_get_multiple_path_params() -> None:
    """GET /tools/users/{uid}/posts/{pid}."""
    f = ApiForge(name="MultiPath")

    @f.tool(method="GET", path="/tools/users/{uid}/posts/{pid}")
    def get_post(uid: int, pid: int) -> dict:
        """Get post."""
        return {"user": uid, "post": pid}

    c = TestClient(f.app)
    resp = c.get("/tools/users/7/posts/99")
    assert resp.status_code == 200
    assert resp.json() == {"user": 7, "post": 99}


# --- POST with path param + body ---

def test_post_path_param_and_body() -> None:
    """POST /tools/users/{uid}/comments with body."""
    f = ApiForge(name="PostPath")

    @f.tool(path="/tools/users/{uid}/comments")
    def add_comment(uid: int, text: str) -> dict:
        """Add comment."""
        return {"user": uid, "comment": text}

    c = TestClient(f.app)
    resp = c.post("/tools/users/5/comments", json={"text": "hello"})
    assert resp.status_code == 200
    assert resp.json() == {"user": 5, "comment": "hello"}


# --- Path param type coercion ---

def test_path_param_string() -> None:
    """String path param works."""
    f = ApiForge(name="StrPath")

    @f.tool(method="GET", path="/tools/repos/{name}")
    def get_repo(name: str) -> dict:
        """Get repo."""
        return {"repo": name}

    c = TestClient(f.app)
    resp = c.get("/tools/repos/my-project")
    assert resp.status_code == 200
    assert resp.json() == {"repo": "my-project"}


# --- Backward compat: no path param still works ---

def test_backward_compat_default_path() -> None:
    """Without path param, default /tools/{name} still works."""
    f = ApiForge(name="Compat")

    @f.tool(method="GET")
    def ping() -> str:
        """Ping."""
        return "pong"

    c = TestClient(f.app)
    resp = c.get("/tools/ping")
    assert resp.status_code == 200
    assert resp.json() == "pong"
