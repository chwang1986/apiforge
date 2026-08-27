"""Prometheus-style metrics, implemented with no external dependencies.

Provides a small in-process metrics registry that can render the
standard Prometheus text exposition format, plus a FastAPI middleware
that auto-instruments request count, latency, and status codes.

Metric types supported:
    - Counter: monotonically increasing (e.g. request total)
    - Histogram: distribution of values (e.g. request latency)
    - Gauge: value that can go up and down (e.g. active connections)

Usage:
    from src.observability.metrics import MetricsRegistry, enable_metrics

    registry = MetricsRegistry(namespace="apiforge")
    enable_metrics(app, registry)
    # GET /metrics -> Prometheus text format
"""

from __future__ import annotations

import time
import threading
from typing import Any

from fastapi import FastAPI, Request, Response


def _sanitize_labels(labels: dict[str, Any]) -> str:
    """Render labels to the Prometheus ``a="1",b="two"`` form."""
    if not labels:
        return ""
    parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
    return ",".join(parts)


class Counter:
    """A monotonically increasing metric.

    Args:
        name: Metric name (e.g. "requests_total").
        documentation: Human readable description.
        label_names: Names of the label keys (used in help/labels docs).
    """

    def __init__(self, name: str, documentation: str = "", label_names: tuple[str, ...] = ()) -> None:
        self.name = name
        self.documentation = documentation
        self.label_names = label_names
        self._values: dict[tuple, float] = {}
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0, **labels: Any) -> None:
        key = tuple(labels.get(n) for n in self.label_names)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def get(self, **labels: Any) -> float:
        key = tuple(labels.get(n) for n in self.label_names)
        return self._values.get(key, 0.0)


class Gauge:
    """A metric that can go up and down."""

    def __init__(self, name: str, documentation: str = "") -> None:
        self.name = name
        self.documentation = documentation
        self._value = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    def get(self) -> float:
        return self._value


class Histogram:
    """A metric that buckets observed values.

    Args:
        name: Metric name.
        documentation: Description.
        buckets: Upper bounds for the buckets.
    """

    DEFAULT_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self, name: str, documentation: str = "", buckets: tuple[float, ...] | None = None) -> None:
        self.name = name
        self.documentation = documentation
        self.buckets = tuple(sorted(buckets or self.DEFAULT_BUCKETS))
        # bucket_upper -> count
        self._counts: dict[float, int] = {b: 0 for b in self.buckets}
        self._inf = 0
        self._sum = 0.0
        self._count = 0
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            placed = False
            for upper in self.buckets:
                if value <= upper:
                    self._counts[upper] += 1
                    placed = True
                    break
            if not placed:
                self._inf += 1
            self._sum += value
            self._count += 1


class MetricsRegistry:
    """Registry that holds and renders all metrics.

    Args:
        namespace: Prefix added to metric names (e.g. "apiforge").
    """

    def __init__(self, namespace: str = "apiforge") -> None:
        self.namespace = namespace
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = threading.Lock()

        # Built-in defaults
        self.counter(
            "http_requests_total",
            "Total HTTP requests",
            label_names=("method", "path", "status"),
        )
        self.histogram("http_request_duration_seconds", "Request latency in seconds")
        self.gauge("http_active_requests", "In-flight requests")

    def counter(self, name: str, documentation: str = "", label_names: tuple[str, ...] = ()) -> Counter:
        full = self._full(name)
        with self._lock:
            if full not in self._counters:
                self._counters[full] = Counter(full, documentation, label_names)
            return self._counters[full]

    def gauge(self, name: str, documentation: str = "") -> Gauge:
        full = self._full(name)
        with self._lock:
            if full not in self._gauges:
                self._gauges[full] = Gauge(full, documentation)
            return self._gauges[full]

    def histogram(self, name: str, documentation: str = "", buckets: tuple[float, ...] | None = None) -> Histogram:
        full = self._full(name)
        with self._lock:
            if full not in self._histograms:
                self._histograms[full] = Histogram(full, documentation, buckets)
            return self._histograms[full]

    def _full(self, name: str) -> str:
        if name.startswith(self.namespace + "_") or name == self.namespace:
            return name
        return f"{self.namespace}_{name}"

    def reset(self) -> None:
        """Clear all counter values and gauge values (useful in tests)."""
        with self._lock:
            for c in self._counters.values():
                c._values.clear()
            for g in self._gauges.values():
                g._value = 0.0
            for h in self._histograms.values():
                for b in h._counts:
                    h._counts[b] = 0
                h._inf = 0
                h._sum = 0.0
                h._count = 0

    def render(self) -> str:
        """Render all metrics in the Prometheus text exposition format."""
        lines: list[str] = []
        for name, counter in self._counters.items():
            if counter.documentation:
                lines.append(f"# HELP {name} {counter.documentation}")
            lines.append(f"# TYPE {name} counter")
            keys = list(counter._values.keys())
            if not keys:
                # Emit an unlabeled 0 line if no labels defined
                if not counter.label_names:
                    lines.append(f"{name} 0")
            for key in keys:
                label_dict = dict(zip(counter.label_names, key))
                label_str = _sanitize_labels(label_dict)
                lines.append(f"{name}{('{' + label_str + '}') if label_str else ''} {counter._values[key]}")
        for name, gauge in self._gauges.items():
            if gauge.documentation:
                lines.append(f"# HELP {name} {gauge.documentation}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {float(gauge.get())}")
        for name, hist in self._histograms.items():
            if hist.documentation:
                lines.append(f"# HELP {name} {hist.documentation}")
            lines.append(f"# TYPE {name} histogram")
            cumulative = 0
            for upper in hist.buckets:
                cumulative += hist._counts[upper]
                lines.append(f'{name}_bucket{{le="{upper}"}} {cumulative}')
            lines.append(f'{name}_bucket{{le="+Inf"}} {hist._count}')
            lines.append(f"{name}_sum {hist._sum}")
            lines.append(f"{name}_count {hist._count}")
        return "\n".join(lines) + "\n"


def enable_metrics(app: FastAPI, registry: MetricsRegistry | None = None) -> MetricsRegistry:
    """Install a /metrics endpoint and request instrumentation middleware.

    Args:
        app: The FastAPI application.
        registry: Optional existing registry (created if omitted).

    Returns:
        The MetricsRegistry in use.
    """
    registry = registry or MetricsRegistry()

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        """Expose metrics in Prometheus text format."""
        return Response(
            content=registry.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        """Instrument every request: count, status, and latency."""
        active = registry.gauge("http_active_requests")
        active.inc()
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            active.dec()
            registry.counter("http_requests_total").inc(
                method=request.method, path=request.url.path, status="500"
            )
            raise
        finally:
            active.dec()

        duration = time.perf_counter() - start
        registry.histogram("http_request_duration_seconds").observe(duration)
        registry.counter("http_requests_total").inc(
            method=request.method,
            path=request.url.path,
            status=str(response.status_code),
        )
        return response

    return registry


def format_histogram_percentile(hist: Histogram, percentile: float) -> float:
    """Approximate a percentile from a histogram's buckets.

    Args:
        hist: The histogram.
        percentile: Percentile in the range 0-100.

    Returns:
        An approximate value (upper bound of the bucket reached).
    """
    if hist._count == 0:
        return 0.0
    target = hist._count * (percentile / 100.0)
    cumulative = 0
    for upper in hist.buckets:
        cumulative += hist._counts[upper]
        if cumulative >= target:
            return upper
    return hist.buckets[-1]
