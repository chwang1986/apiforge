"""Round 31: Python client SDK generation tests."""

import pytest
from src.server import ApiForge
from src.codegen.client import generate_client, generate_client_code, _type_hint, _build_method_name


# --- _type_hint ---

def test_type_hint_mapping() -> None:
    assert _type_hint({"type": "string"}) == "str"
    assert _type_hint({"type": "integer"}) == "int"
    assert _type_hint({"type": "number"}) == "float"
    assert _type_hint({"type": "boolean"}) == "bool"
    assert _type_hint({"type": "array"}) == "list[Any]"
    assert _type_hint({"type": "object"}) == "dict[str, Any]"
    assert _type_hint({}) == "str"


# --- _build_method_name ---

def test_build_method_name_unique() -> None:
    seen: set[str] = set()
    name1 = _build_method_name({"operationId": "add"}, "/tools/add", seen)
    name2 = _build_method_name({"operationId": "add"}, "/tools/add2", seen)
    assert name1 == "add"
    assert name2 == "add_2"
    assert name1 != name2


# --- generate_client_code basic ---

def test_generated_code_syntax_valid() -> None:
    """Generated code compiles without errors."""
    f = ApiForge(name="CodeGen")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    code = generate_client(f.app, client_name="MyClient")
    compile(code, "<gen>", "exec")


def test_generated_code_has_class() -> None:
    """Generated code contains the class."""
    f = ApiForge(name="ClassTest")

    @f.tool
    def ping() -> str:
        """Ping."""
        return "pong"

    code = generate_client(f.app, client_name="PingClient")
    assert "class PingClient:" in code
    assert "httpx" in code
    assert "base_url" in code


def test_generated_code_has_method() -> None:
    """Generated code has a method for each tool."""
    f = ApiForge(name="MethodTest")

    @f.tool
    def compute(x: int) -> int:
        """Compute."""
        return x * 2

    code = generate_client(f.app, client_name="CalcClient")
    # Method should reference the tool path
    assert "/tools/compute" in code


def test_generated_code_multiple_tools() -> None:
    """Multiple tools generate multiple methods."""
    f = ApiForge(name="Multi")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    @f.tool
    def sub(a: int, b: int) -> int:
        """Sub."""
        return a - b

    code = generate_client(f.app, client_name="MathClient")
    assert "/tools/add" in code
    assert "/tools/sub" in code
    compile(code, "<gen>", "exec")


def test_generated_code_from_spec_dict() -> None:
    """Can generate from a raw spec dict."""
    spec = {
        "info": {"title": "Raw", "version": "1.0"},
        "paths": {
            "/tools/echo": {
                "post": {
                    "operationId": "echo",
                    "summary": "Echo text",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "properties": {"text": {"type": "string"}}
                                }
                            }
                        }
                    },
                }
            }
        },
    }
    code = generate_client(spec, client_name="EchoClient")
    assert "class EchoClient:" in code
    assert "text" in code
    compile(code, "<gen>", "exec")


def test_generated_code_api_key_support() -> None:
    """Generated code includes API key support."""
    f = ApiForge(name="Auth")

    @f.tool
    def secret(x: str) -> str:
        """Secret."""
        return x

    code = generate_client(f.app, client_name="AuthClient")
    assert "api_key" in code
    assert "Authorization" in code
    assert "Bearer" in code
