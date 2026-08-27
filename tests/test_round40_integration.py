"""Round 40: Comprehensive integration tests.

Verifies multiple ApiForge features working together in a single instance:
- Tools + GET + transforms
- OpenAPI (summary + examples)
- Namespace
- Error handling (ToolError -> 400)
- Health checks
- Codegen (client + curl)
- Plugins
- API keys
- Testing utilities
- Envelope mode
"""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.transform import strip_strings, wrap_in_key
from src.plugins import Plugin, PluginRegistry
from src.api_keys import KeyManager
from src.errors import ToolError
from src.testing import post_tool, get_tool
from src.codegen.client import generate_client
from src.codegen.curl import generate_curl


def _envelope(data):
    """Expected envelope format for envelope=True responses."""
    return {"status": "ok", "data": data, "meta": {}}


def _build_full_stack() -> ApiForge:
    """Build a single ApiForge with many features combined (envelope=True)."""
    f = ApiForge(
        name="FullStack",
        description="Comprehensive integration test service",
        envelope=True,
    )

    @f.tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @f.tool(before=strip_strings, after=wrap_in_key("result"))
    def process(text: str) -> str:
        """Process text."""
        return text.upper()

    @f.tool(method="GET")
    def health_check() -> dict:
        """Get health."""
        return {"status": "ok"}

    @f.tool(
        summary="Multiply numbers",
        examples={"default": {"value": {"x": 3, "y": 4}}},
    )
    def multiply(x: int, y: int) -> int:
        """Multiply."""
        return x * y

    @f.tool
    def always_fail() -> str:
        """Always fails."""
        raise ToolError("intentional error", code="INTENTIONAL_FAIL")

    users = f.namespace("users")

    @users.tool
    def get_user(name: str) -> dict:
        """Get a user."""
        return {"name": name, "id": hash(name) % 10000}

    return f


# --- Test: all tools work ---

def test_all_tools_functional() -> None:
    """All tools respond correctly in envelope mode."""
    f = _build_full_stack()
    c = TestClient(f.app)

    assert c.post("/tools/add", json={"a": 1, "b": 2}).json()["data"] == 3
    # Transform wraps in {"result": ...}
    resp = c.post("/tools/process", json={"text": "  hello  "})
    assert resp.json()["data"] == {"result": "HELLO"}
    # GET
    assert c.get("/tools/health_check").json()["data"] == {"status": "ok"}
    # Summary tool
    assert c.post("/tools/multiply", json={"x": 6, "y": 7}).json()["data"] == 42
    # Namespace
    resp = c.post("/users/get_user", json={"name": "alice"})
    assert resp.json()["data"]["name"] == "alice"


def test_error_handling_toolerror() -> None:
    """ToolError returns 400 with structured error body."""
    f = _build_full_stack()
    c = TestClient(f.app)
    resp = c.post("/tools/always_fail", json={})
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "INTENTIONAL_FAIL"


def test_openapi_includes_all() -> None:
    """OpenAPI spec has all endpoints with correct metadata."""
    f = _build_full_stack()
    c = TestClient(f.app)
    spec = c.get("/api/openapi.json").json()

    assert "/tools/add" in spec["paths"]
    assert "/tools/process" in spec["paths"]
    assert "/tools/health_check" in spec["paths"]
    assert "/tools/multiply" in spec["paths"]
    assert "/users/get_user" in spec["paths"]

    op = spec["paths"]["/tools/multiply"]["post"]
    assert op["summary"] == "Multiply numbers"
    assert op["requestBody"]["examples"]["default"]["value"] == {"x": 3, "y": 4}

    user_op = spec["paths"]["/users/get_user"]["post"]
    assert "users" in user_op.get("tags", [])


def test_health_endpoint() -> None:
    """Built-in /health works."""
    f = _build_full_stack()
    c = TestClient(f.app)
    resp = c.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "FullStack"


# --- Codegen with full stack ---

def test_codegen_client_full_stack() -> None:
    """Generated client covers all tools."""
    f = _build_full_stack()
    code = generate_client(f.app, client_name="FullStackClient")
    assert "class FullStackClient:" in code
    assert "/tools/add" in code
    assert "/tools/multiply" in code
    assert "/users/get_user" in code
    compile(code, "<gen>", "exec")


def test_codegen_curl_full_stack() -> None:
    """Generated curl covers all tools."""
    f = _build_full_stack()
    spec = f.app.openapi()
    commands = generate_curl(spec)
    assert len(commands) >= 5
    for name, cmd in commands.items():
        assert cmd.startswith("curl")


# --- Plugins with full stack ---

def test_plugin_system_integration() -> None:
    """Plugins execute in order; disable skips hooks."""
    calls: list[str] = []

    def hook_1(ctx):
        calls.append("hook_1")

    def hook_2(ctx):
        calls.append("hook_2")

    registry = PluginRegistry()
    registry.register(Plugin(name="p1", hooks={"before_request": hook_1}))
    registry.register(Plugin(name="p2", hooks={"before_request": hook_2}))

    registry.execute("before_request", ctx={"path": "/tools/add"})
    assert calls == ["hook_1", "hook_2"]

    registry.disable("p1")
    calls.clear()
    registry.execute("before_request", ctx={})
    assert calls == ["hook_2"]


# --- API keys with full stack ---

def test_api_key_integration() -> None:
    """API keys lifecycle works independently of tools."""
    km = KeyManager(secret="test-secret")
    key = km.generate("integration-test", ttl_hours=24)
    info = km.validate(key)
    assert info.name == "integration-test"

    new_key = km.rotate(key)
    assert new_key != key
    with pytest.raises(ValueError):
        km.validate(key)
    assert km.validate(new_key).name == "integration-test"


# --- Testing utilities with full stack ---

def test_testing_utils_integration() -> None:
    """Testing helpers work on a complex instance."""
    f = _build_full_stack()
    result = post_tool(f, "add", {"a": 10, "b": 20})
    assert result["data"] == 30

    result = get_tool(f, "health_check")
    assert result["data"] == {"status": "ok"}


# --- Envelope modes ---

def test_envelope_mode() -> None:
    """envelope=True wraps responses in status/data/meta."""
    f = ApiForge(name="Env", envelope=True)

    @f.tool
    def echo(msg: str) -> str:
        """Echo."""
        return msg

    c = TestClient(f.app)
    body = c.post("/tools/echo", json={"msg": "hi"}).json()
    assert body["status"] == "ok"
    assert body["data"] == "hi"
    assert "meta" in body


def test_no_envelope_mode() -> None:
    """envelope=False (default) returns raw response."""
    f = ApiForge(name="Raw")

    @f.tool
    def echo(msg: str) -> str:
        """Echo."""
        return msg

    c = TestClient(f.app)
    assert c.post("/tools/echo", json={"msg": "hi"}).json() == "hi"


# --- Many tools ---

def test_many_tools_no_conflict() -> None:
    """Many tools don't conflict with each other."""
    f = ApiForge(name="Many")

    for i in range(10):
        def make_tool(n):
            def tool(x: int) -> int:
                """Tool."""
                return x + n
            tool.__name__ = f"tool_{i}"
            return tool
        f.tool(make_tool(i))

    c = TestClient(f.app)
    for i in range(10):
        resp = c.post(f"/tools/tool_{i}", json={"x": 1})
        assert resp.status_code == 200
        assert resp.json() == 1 + i


# --- Summary: full stack works together ---

def test_full_stack_summary() -> None:
    """Final integration: everything works in one instance."""
    f = _build_full_stack()
    c = TestClient(f.app)

    assert c.post("/tools/add", json={"a": 5, "b": 5}).status_code == 200
    assert c.post("/tools/process", json={"text": "x"}).status_code == 200
    assert c.get("/tools/health_check").status_code == 200
    assert c.post("/users/get_user", json={"name": "bob"}).status_code == 200

    spec = c.get("/api/openapi.json").json()
    assert len(spec["paths"]) >= 6

    assert c.get("/health").status_code == 200
    assert c.post("/tools/always_fail", json={}).status_code == 400

    code = generate_client(f.app)
    compile(code, "<gen>", "exec")
