"""Round 41: Prometheus Metrics tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    enable_metrics,
    format_histogram_percentile,
)


# --- Counter ---

def test_counter_inc() -> None:
    c = Counter("test_total", "Test", ("method",))
    c.inc(method="GET")
    c.inc(method="GET", amount=2)
    c.inc(method="POST")
    assert c.get(method="GET") == 3
    assert c.get(method="POST") == 1


def test_counter_default_zero() -> None:
    c = Counter("empty_total")
    assert c.get() == 0.0


# --- Gauge ---

def test_gauge_set_inc_dec() -> None:
    g = Gauge("active", "Active")
    g.set(10)
    assert g.get() == 10
    g.inc(5)
    assert g.get() == 15
    g.dec(3)
    assert g.get() == 12


# --- Histogram ---

def test_histogram_observe() -> None:
    h = Histogram("latency", "Latency")
    h.observe(0.001)
    h.observe(0.05)
    h.observe(5.0)
    assert h._count == 3
    assert h._sum == pytest.approx(5.051)


def test_histogram_buckets() -> None:
    h = Histogram("lat", "", buckets=(0.1, 1.0, 10.0))
    h.observe(0.05)   # <= 0.1
    h.observe(0.5)    # <= 1.0
    h.observe(50.0)   # > 10.0
    assert h._counts[0.1] == 1
    assert h._counts[1.0] == 1
    assert h._counts[10.0] == 0
    assert h._inf == 1


def test_format_histogram_percentile() -> None:
    h = Histogram("p", "", buckets=(0.1, 1.0, 10.0))
    h.observe(0.05)
    h.observe(0.5)
    h.observe(5.0)
    p50 = format_histogram_percentile(h, 50)
    assert p50 in (0.1, 1.0, 10.0)


# --- MetricsRegistry ---

def test_registry_namespace() -> None:
    r = MetricsRegistry(namespace="myapp")
    c = r.counter("requests_total")
    assert c.name == "myapp_requests_total"


def test_registry_builtin_metrics() -> None:
    r = MetricsRegistry()
    assert r.gauge("http_active_requests") is not None
    assert r.histogram("http_request_duration_seconds") is not None
    c = r.counter("http_requests_total")
    assert c.label_names == ("method", "path", "status")


def test_registry_render_prometheus_format() -> None:
    r = MetricsRegistry(namespace="test")
    c = r.counter("hits_total", "Total hits")
    c.inc()
    g = r.gauge("active", "Active")
    g.set(42)
    h = r.histogram("dur", "Duration")
    h.observe(0.05)

    output = r.render()
    assert "# TYPE test_hits_total counter" in output
    assert "# TYPE test_active gauge" in output
    assert "# TYPE test_dur histogram" in output
    assert "test_hits_total 1.0" in output
    assert "test_active 42.0" in output
    assert "test_dur_bucket" in output
    assert "test_dur_count 1" in output


def test_registry_reset() -> None:
    r = MetricsRegistry(namespace="r")
    c = r.counter("n_total", label_names=("x",))
    c.inc(x="a", amount=5)
    g = r.gauge("v")
    g.set(100)
    r.reset()
    assert c.get(x="a") == 0.0
    assert g.get() == 0.0


# --- enable_metrics integration ---

def test_metrics_endpoint() -> None:
    f = ApiForge(name="Metrics")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    enable_metrics(f.app)
    c = TestClient(f.app)

    # Make some requests
    c.post("/tools/add", json={"a": 1, "b": 2})
    c.post("/tools/add", json={"a": 3, "b": 4})

    # Check /metrics
    resp = c.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "apiforge_http_requests_total" in body
    assert 'status="200"' in body
    assert "apiforge_http_request_duration_seconds_count" in body


def test_metrics_increments_per_request() -> None:
    f = ApiForge(name="Incr")

    @f.tool
    def ping() -> str:
        """Ping."""
        return "pong"

    registry = enable_metrics(f.app)
    c = TestClient(f.app)

    c.post("/tools/ping", json={})
    c.post("/tools/ping", json={})
    c.get("/health")

    count = registry.counter("http_requests_total").get(
        method="POST", path="/tools/ping", status="200"
    )
    assert count == 2


def test_metrics_histogram_observations() -> None:
    f = ApiForge(name="Hist")

    @f.tool
    def slow() -> str:
        """Slow."""
        return "ok"

    registry = enable_metrics(f.app)
    c = TestClient(f.app)

    c.post("/tools/slow", json={})
    h = registry.histogram("http_request_duration_seconds")
    assert h._count == 1
    assert h._sum > 0
