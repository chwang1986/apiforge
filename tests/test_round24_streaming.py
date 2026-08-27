"""Round 24: SSE streaming response tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src._internal import is_streaming_tool


# --- is_streaming_tool detection ---

def test_is_streaming_tool_true() -> None:
    """Async generator function is detected as streaming."""
    async def stream():
        """Stream."""
        yield "chunk1"
        yield "chunk2"

    assert is_streaming_tool(stream) is True


def test_is_streaming_tool_false() -> None:
    """Regular async function is not streaming."""
    async def normal() -> str:
        """Normal."""
        return "ok"

    assert is_streaming_tool(normal) is False


def test_is_streaming_tool_false_sync() -> None:
    """Sync function is not streaming."""
    def sync_func() -> str:
        """Sync."""
        return "ok"

    assert is_streaming_tool(sync_func) is False


# --- Basic SSE streaming ---

def test_sse_streaming_basic() -> None:
    """SSE streaming returns text/event-stream with data events."""
    f = ApiForge(name="SSE")

    @f.tool
    async def stream_words():
        """Stream words one by one."""
        for word in ["hello", "world", "api"]:
            yield word

    c = TestClient(f.app)
    resp = c.post("/tools/stream_words", json={})
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("text/event-stream")
    # Each chunk is a "data: ..." line
    body = resp.text
    assert "data: hello" in body
    assert "data: world" in body
    assert "data: api" in body
    # Ends with [DONE]
    assert "data: [DONE]" in body


def test_sse_streaming_with_params() -> None:
    """SSE streaming accepts JSON body params."""
    f = ApiForge(name="SSE Params")

    @f.tool
    async def count(n: int):
        """Stream numbers 1 to n."""
        for i in range(1, n + 1):
            yield f"number_{i}"

    c = TestClient(f.app)
    resp = c.post("/tools/count", json={"n": 3})
    assert resp.status_code == 200
    body = resp.text
    assert "data: number_1" in body
    assert "data: number_2" in body
    assert "data: number_3" in body
    assert "data: [DONE]" in body


def test_sse_streaming_dict_chunks() -> None:
    """SSE streaming with dict chunks (JSON-encoded)."""
    f = ApiForge(name="SSE Dict")

    @f.tool
    async def stream_data():
        """Stream dict objects."""
        yield {"id": 1, "msg": "first"}
        yield {"id": 2, "msg": "second"}

    c = TestClient(f.app)
    resp = c.post("/tools/stream_data", json={})
    assert resp.status_code == 200
    body = resp.text
    assert '"id": 1' in body or '"id":1' in body
    assert '"msg": "first"' in body or '"msg":"first"' in body


# --- Streaming doesn't break other tools ---

def test_regular_tools_unaffected() -> None:
    """Normal tools work alongside streaming tools."""
    f = ApiForge(name="Mixed SSE")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    @f.tool
    async def stream():
        """Stream."""
        yield "a"
        yield "b"

    c = TestClient(f.app)
    # Regular
    resp = c.post("/tools/add", json={"a": 1, "b": 2})
    assert resp.status_code == 200
    assert resp.json() == 3

    # Streaming
    resp = c.post("/tools/stream", json={})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_sse_headers() -> None:
    """SSE response has correct headers."""
    f = ApiForge(name="SSE Headers")

    @f.tool
    async def stream():
        """Stream."""
        yield "x"

    c = TestClient(f.app)
    resp = c.post("/tools/stream", json={})
    assert resp.status_code == 200
    ct = resp.headers.get("content-type", "")
    assert "text/event-stream" in ct
    assert resp.headers.get("cache-control") == "no-cache"
