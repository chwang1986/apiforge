"""Round 26: Tool pipeline tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.pipeline import Pipeline


# --- Pipeline unit tests ---

def test_pipeline_basic_execute() -> None:
    """Pipeline executes steps sequentially."""
    def double(x: int) -> int:
        return x * 2

    def add_one(x: int) -> int:
        return x + 1

    p = Pipeline(steps=[double, add_one], name="test")
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(p.execute(5))
    assert result == 11  # (5 * 2) + 1


def test_pipeline_single_step() -> None:
    """Pipeline with one step works."""
    def shout(s: str) -> str:
        return s.upper() + "!"

    p = Pipeline(steps=[shout], name="shout")
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(p.execute("hi"))
    assert result == "HI!"


def test_pipeline_empty_raises() -> None:
    """Empty pipeline raises ValueError."""
    with pytest.raises(ValueError):
        Pipeline(steps=[])


def test_pipeline_async_step() -> None:
    """Pipeline with async steps works."""
    async def async_double(x: int) -> int:
        return x * 2

    def add_one(x: int) -> int:
        return x + 1

    p = Pipeline(steps=[async_double, add_one], name="async")
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(p.execute(3))
    assert result == 7  # (3 * 2) + 1


def test_pipeline_len() -> None:
    """Pipeline reports step count."""
    p = Pipeline(steps=[lambda x: x, lambda x: x], name="two")
    assert len(p) == 2


# --- Integration: forge.pipeline ---

def test_forge_pipeline_endpoint() -> None:
    """Pipeline registered via forge.pipeline works end-to-end."""
    f = ApiForge(name="Pipeline")

    def clean(text: str) -> str:
        return text.strip().lower()

    def shout(text: str) -> str:
        return text.upper() + "!"

    def exclaim(text: str) -> str:
        return text + "???"

    f.pipeline(steps=[clean, shout, exclaim], name="transform", input_type=str)

    c = TestClient(f.app)
    resp = c.post("/tools/transform", json={"input": "  hello world  "})
    assert resp.status_code == 200
    assert resp.json() == "HELLO WORLD!???"


def test_pipeline_with_int_input() -> None:
    """Pipeline works with int input."""
    f = ApiForge(name="Pipe Int")

    def square(x: int) -> int:
        return x * x

    def root(x: int) -> int:
        return int(x ** 0.5)

    f.pipeline(steps=[square, root], name="identity", input_type=int)

    c = TestClient(f.app)
    resp = c.post("/tools/identity", json={"input": 9})
    assert resp.status_code == 200
    assert resp.json() == 9  # 9 -> 81 -> int(sqrt(81)) = 9


def test_pipeline_error_in_step() -> None:
    """Error in a pipeline step returns structured error."""
    f = ApiForge(name="Pipe Error")

    def ok_step(x: str) -> str:
        return x

    def bad_step(x: str) -> str:
        raise ValueError("step failed")

    f.pipeline(steps=[ok_step, bad_step], name="broken")

    c = TestClient(f.app, raise_server_exceptions=False)
    resp = c.post("/tools/broken", json={"input": "test"})
    assert resp.status_code >= 400


def test_pipeline_coexists_with_tools() -> None:
    """Pipeline and regular tools coexist."""
    f = ApiForge(name="Pipe Mixed")

    @f.tool
    def add(a: int, b: int) -> int:
        return a + b

    def upper(s: str) -> str:
        return s.upper()

    f.pipeline(steps=[upper], name="shout", input_type=str)

    c = TestClient(f.app)
    # Regular tool
    assert c.post("/tools/add", json={"a": 1, "b": 2}).json() == 3
    # Pipeline
    assert c.post("/tools/shout", json={"input": "hi"}).json() == "HI"
