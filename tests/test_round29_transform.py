"""Round 29: Request/Response transform tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.transform import wrap_tool, to_upper, to_lower, strip_strings, wrap_in_key, identity


# --- wrap_tool unit tests ---

def test_wrap_tool_before_only() -> None:
    """Before transform modifies kwargs."""
    def double(kwargs: dict) -> dict:
        return {k: v * 2 for k, v in kwargs.items()}

    def add(a: int, b: int) -> int:
        return a + b

    wrapped = wrap_tool(add, before=double)
    assert wrapped(a=1, b=2) == 6  # (1*2) + (2*2) = 6


def test_wrap_tool_after_only() -> None:
    """After transform modifies result."""
    def triple(x: int) -> int:
        return x * 3

    def add(a: int, b: int) -> int:
        return a + b

    wrapped = wrap_tool(add, after=triple)
    assert wrapped(a=1, b=2) == 9  # (1+2)*3 = 9


def test_wrap_tool_both() -> None:
    """Before and after transforms chain."""
    def upper(kwargs: dict) -> dict:
        return {k: v.upper() for k, v in kwargs.items()}

    def exclaim(s: str) -> str:
        return s + "!"

    def echo(text: str) -> str:
        return text.strip()

    wrapped = wrap_tool(echo, before=upper, after=exclaim)
    assert wrapped(text="  hello  ") == "HELLO!"


def test_wrap_tool_noop() -> None:
    """No transforms returns original function."""
    def echo(text: str) -> str:
        return text

    result = wrap_tool(echo)
    assert result is echo


# --- Integration: forge.tool with before/after ---

def test_forge_tool_with_before() -> None:
    """Tool with before transform via forge.tool()."""
    f = ApiForge(name="Transform Before")

    @f.tool(before=strip_strings)
    def process(text: str) -> str:
        """Process text."""
        return text

    c = TestClient(f.app)
    resp = c.post("/tools/process", json={"text": "  hello  "})
    assert resp.status_code == 200
    assert resp.json() == "hello"


def test_forge_tool_with_after() -> None:
    """Tool with after transform via forge.tool()."""
    f = ApiForge(name="Transform After")

    @f.tool(after=wrap_in_key("result"))
    def compute(a: int, b: int) -> int:
        """Add numbers."""
        return a + b

    c = TestClient(f.app)
    resp = c.post("/tools/compute", json={"a": 3, "b": 4})
    assert resp.status_code == 200
    assert resp.json() == {"result": 7}


def test_forge_tool_before_and_after() -> None:
    """Tool with both before and after transforms."""
    f = ApiForge(name="Transform Both")

    @f.tool(before=strip_strings, after=wrap_in_key("data"))
    def shout(text: str) -> str:
        """Uppercase text."""
        return text.upper()

    c = TestClient(f.app)
    resp = c.post("/tools/shout", json={"text": "  hi  "})
    assert resp.status_code == 200
    assert resp.json() == {"data": "HI"}


def test_transform_builtin_to_upper() -> None:
    """Builtin to_upper works on kwargs."""
    result = to_upper({"name": "bob", "age": 5})
    assert result == {"name": "BOB", "age": 5}


def test_transforms_dont_break_regular_tools() -> None:
    """Tools without transforms still work normally."""
    f = ApiForge(name="NoTransform")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    c = TestClient(f.app)
    resp = c.post("/tools/add", json={"a": 1, "b": 2})
    assert resp.status_code == 200
    assert resp.json() == 3
