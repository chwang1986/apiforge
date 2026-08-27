"""Round 25: WebSocket tool tests."""

import json
import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient

from src.server import ApiForge


# --- Basic echo ---

def test_ws_echo() -> None:
    """WebSocket echo: send a message, get it back."""
    f = ApiForge(name="WS Echo")

    @f.ws
    async def echo(websocket: WebSocket):
        """Echo messages back."""
        await websocket.accept()
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")

    c = TestClient(f.app)
    with c.websocket_connect("/ws/echo") as ws:
        ws.send_text("hello")
        resp = ws.receive_text()
        assert resp == "Echo: hello"


# --- JSON messages ---

def test_ws_json() -> None:
    """WebSocket handles JSON messages."""
    f = ApiForge(name="WS JSON")

    @f.ws
    async def calc(websocket: WebSocket):
        """Calculate sum from JSON."""
        await websocket.accept()
        data = json.loads(await websocket.receive_text())
        result = {"sum": data["a"] + data["b"]}
        await websocket.send_text(json.dumps(result))

    c = TestClient(f.app)
    with c.websocket_connect("/ws/calc") as ws:
        ws.send_text(json.dumps({"a": 3, "b": 7}))
        resp = json.loads(ws.receive_text())
        assert resp["sum"] == 10


# --- Multiple messages ---

def test_ws_multi_message() -> None:
    """WebSocket handles multiple messages in sequence."""
    f = ApiForge(name="WS Multi")

    @f.ws
    async def counter(websocket: WebSocket):
        """Count messages received."""
        await websocket.accept()
        count = 0
        while True:
            data = await websocket.receive_text()
            if data == "stop":
                break
            count += 1
            await websocket.send_text(f"count={count}")

    c = TestClient(f.app)
    with c.websocket_connect("/ws/counter") as ws:
        ws.send_text("1")
        assert ws.receive_text() == "count=1"
        ws.send_text("2")
        assert ws.receive_text() == "count=2"
        ws.send_text("stop")


# --- Custom path ---

def test_ws_custom_path() -> None:
    """WebSocket with custom path."""
    f = ApiForge(name="WS Path")

    @f.ws(path="/custom/endpoint")
    async def custom(websocket: WebSocket):
        """Custom path handler."""
        await websocket.accept()
        data = await websocket.receive_text()
        await websocket.send_text(f"custom: {data}")

    c = TestClient(f.app)
    with c.websocket_connect("/custom/endpoint") as ws:
        ws.send_text("test")
        assert ws.receive_text() == "custom: test"


# --- WS alongside regular tools ---

def test_ws_with_regular_tools() -> None:
    """WebSocket and HTTP tools coexist."""
    f = ApiForge(name="WS Mixed")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    @f.ws
    async def chat(websocket: WebSocket):
        """Chat."""
        await websocket.accept()
        data = await websocket.receive_text()
        await websocket.send_text(f"reply: {data}")

    c = TestClient(f.app)
    # HTTP tool
    resp = c.post("/tools/add", json={"a": 1, "b": 2})
    assert resp.status_code == 200
    assert resp.json() == 3

    # WS tool
    with c.websocket_connect("/ws/chat") as ws:
        ws.send_text("hi")
        assert ws.receive_text() == "reply: hi"

    # Health still works
    resp = c.get("/health")
    assert resp.status_code == 200
