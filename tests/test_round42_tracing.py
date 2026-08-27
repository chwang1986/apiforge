"""Round 42: Distributed tracing tests."""

import json
import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.observability.tracing import (
    Span,
    Tracer,
    TraceContext,
    enable_tracing,
)


# --- Span dataclass ---

def test_span_fields() -> None:
    s = Span(trace_id="t1", span_id="s1", name="test", start_time=100.0, end_time=100.5)
    assert s.trace_id == "t1"
    assert s.span_id == "s1"
    assert s.duration_ms == pytest.approx(500.0, abs=1)
    assert s.status == "unset"


def test_span_to_dict() -> None:
    s = Span(trace_id="t1", span_id="s1", name="op", start_time=0, end_time=1)
    d = s.to_dict()
    assert d["trace_id"] == "t1"
    assert d["span_id"] == "s1"
    assert d["name"] == "op"
    assert d["duration_ms"] > 0


# --- TraceContext ---

def test_trace_context_to_headers() -> None:
    ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
    headers = ctx.to_headers()
    assert "traceparent" in headers
    assert f"a" * 32 in headers["traceparent"]


def test_trace_context_from_headers() -> None:
    ctx = TraceContext.from_headers({
        "traceparent": f"00-{'c' * 32}-{'d' * 16}-01"
    })
    assert ctx is not None
    assert ctx.trace_id == "c" * 32
    assert ctx.span_id == "d" * 16


def test_trace_context_from_invalid_headers() -> None:
    assert TraceContext.from_headers({}) is None
    assert TraceContext.from_headers({"traceparent": "garbage"}) is None


# --- Tracer ---

def test_tracer_start_end_span() -> None:
    t = Tracer(service_name="test-svc")
    span = t.start_span("operation", key="val")
    assert span.end_time is None
    assert span.attributes["service"] == "test-svc"
    assert span.attributes["key"] == "val"

    t.end_span(span, status="ok")
    assert span.end_time is not None
    assert span.status == "ok"
    assert len(t) == 1


def test_tracer_nested_spans() -> None:
    t = Tracer()
    parent = t.start_span("parent")
    child = t.start_span("child", trace_id=parent.trace_id, parent_id=parent.span_id)
    t.end_span(child, status="ok")
    t.end_span(parent, status="ok")

    traces = t.get_traces()
    assert len(traces) == 1
    assert traces[0]["span_count"] == 2
    # Find the child span and verify parent link
    spans = traces[0]["spans"]
    child_span = next(s for s in spans if s["name"] == "child")
    assert child_span["parent_id"] == parent.span_id


def test_tracer_max_spans() -> None:
    t = Tracer(max_spans=5)
    for i in range(10):
        s = t.start_span(f"op_{i}")
        t.end_span(s)
    assert len(t) == 5


def test_tracer_clear() -> None:
    t = Tracer()
    s = t.start_span("x")
    t.end_span(s)
    assert len(t) == 1
    t.clear()
    assert len(t) == 0


# --- enable_tracing integration ---

def test_tracing_endpoint() -> None:
    f = ApiForge(name="Tracing")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    tracer = enable_tracing(f.app)
    c = TestClient(f.app)

    # Make requests
    c.post("/tools/add", json={"a": 1, "b": 2})
    c.get("/health")

    # Check /traces
    resp = c.get("/traces")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "trace_id" in data[0]
    assert "spans" in data[0]


def test_tracing_response_headers() -> None:
    f = ApiForge(name="Headers")

    @f.tool
    def ping() -> str:
        """Ping."""
        return "pong"

    enable_tracing(f.app)
    c = TestClient(f.app)
    resp = c.post("/tools/ping", json={})
    # traceparent header should be in response
    assert "traceparent" in resp.headers


def test_tracing_continues_from_header() -> None:
    f = ApiForge(name="Continue")

    @f.tool
    def echo(msg: str) -> str:
        """Echo."""
        return msg

    tracer = enable_tracing(f.app)
    c = TestClient(f.app)

    # Simulate incoming trace from upstream service
    upstream_trace = "f" * 32
    upstream_span = "e" * 16
    resp = c.post(
        "/tools/echo",
        json={"msg": "hi"},
        headers={"traceparent": f"00-{upstream_trace}-{upstream_span}-01"},
    )
    assert resp.status_code == 200

    # The trace should have our trace_id = upstream_trace
    traces = tracer.get_traces()
    assert any(t["trace_id"] == upstream_trace for t in traces)


def test_tracing_error_span() -> None:
    f = ApiForge(name="Err")
    from src.errors import ToolError

    @f.tool
    def fail() -> str:
        """Fail."""
        raise ToolError("oops")

    tracer = enable_tracing(f.app)
    c = TestClient(f.app)
    c.post("/tools/fail", json={})

    traces = tracer.get_traces()
    assert len(traces) >= 1
