"""Round 32: cURL command generator tests."""

import json
import pytest
from src.server import ApiForge
from src.codegen.curl import (
    generate_curl,
    generate_curl_commands,
    generate_curl_for_operation,
    _build_example_body,
)


# --- _build_example_body ---

def test_build_example_body_types() -> None:
    """Example body has correct types per schema."""
    props = {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "score": {"type": "number"},
        "active": {"type": "boolean"},
        "tags": {"type": "array"},
        "meta": {"type": "object"},
    }
    body = _build_example_body(props)
    assert body["name"] == "example"
    assert body["age"] == 1
    assert body["score"] == 1.0
    assert body["active"] is True
    assert body["tags"] == []
    assert body["meta"] == {}


# --- Single operation ---

def test_curl_post_with_body() -> None:
    """POST generates curl with -d body."""
    f = ApiForge(name="CurlTest")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    spec = f.app.openapi()
    ops = spec["paths"]["/tools/add"]["post"]
    cmd = generate_curl_for_operation("POST", "/tools/add", ops, spec=spec)
    assert "curl -X POST" in cmd
    assert "/tools/add" in cmd
    assert "-d " in cmd
    assert "Content-Type: application/json" in cmd


def test_curl_post_from_app() -> None:
    """generate_curl() works with FastAPI app."""
    f = ApiForge(name="CurlApp")

    @f.tool
    def multiply(a: int, b: int) -> int:
        """Multiply."""
        return a * b

    commands = generate_curl(f.app)
    assert len(commands) >= 1
    for name, cmd in commands.items():
        assert cmd.startswith("curl")


# --- API key in curl ---

def test_curl_with_api_key() -> None:
    """API key adds Authorization header."""
    f = ApiForge(name="CurlAuth")

    @f.tool
    def secret(x: str) -> str:
        """Secret."""
        return x

    spec = f.app.openapi()
    ops = spec["paths"]["/tools/secret"]["post"]
    cmd = generate_curl_for_operation("POST", "/tools/secret", ops, api_key="sk-test-123", spec=spec)
    assert "Authorization: Bearer sk-test-123" in cmd


# --- Path params in curl ---

def test_curl_path_params() -> None:
    """Path params become <param> placeholders."""
    f = ApiForge(name="CurlPath")

    @f.tool(method="GET", path="/tools/users/{user_id}")
    def get_user(user_id: int) -> dict:
        """Get user."""
        return {"id": user_id}

    spec = f.app.openapi()
    ops = spec["paths"]["/tools/users/{user_id}"]["get"]
    cmd = generate_curl_for_operation("GET", "/tools/users/{user_id}", ops, spec=spec)
    assert "<user_id>" in cmd


# --- Multiple tools ---

def test_curl_multiple_tools() -> None:
    """Multiple tools generate multiple commands."""
    f = ApiForge(name="CurlMulti")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    @f.tool
    def sub(a: int, b: int) -> int:
        """Sub."""
        return a - b

    commands = generate_curl(f.app)
    assert len(commands) >= 2


# --- GET has no body ---

def test_curl_get_no_body() -> None:
    """GET request doesn't include -d body."""
    f = ApiForge(name="CurlGet")

    @f.tool(method="GET")
    def list_items() -> list:
        """List."""
        return []

    spec = f.app.openapi()
    ops = spec["paths"]["/tools/list_items"]["get"]
    cmd = generate_curl_for_operation("GET", "/tools/list_items", ops, spec=spec)
    assert "-d " not in cmd


# --- generate_curl_commands from dict spec ---

def test_curl_commands_from_dict() -> None:
    """Works with raw spec dict."""
    spec = {
        "info": {"title": "T", "version": "1"},
        "paths": {
            "/tools/ping": {
                "post": {
                    "operationId": "ping",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"properties": {"msg": {"type": "string"}}}
                            }
                        }
                    },
                }
            }
        },
    }
    commands = generate_curl_commands(spec)
    assert "ping" in commands
    assert "curl" in commands["ping"]
