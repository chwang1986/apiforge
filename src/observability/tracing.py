"""ApiForge distributed tracing (simplified OpenTelemetry-style spans).

No external dependencies. Provides:
    - Span: a unit of work with name, start/end, attributes
    - TraceContext: propagates trace_id + span_id across service boundaries
    - Tracer: creates spans, records timing, renders trace data

Usage:
    from src.observability.tracing import Tracer, enable_tracing

    tracer = Tracer(service_name="my-service")
    enable_tracing(app, tracer)
    # GET /traces -> JSON trace data
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request, Response


def _gen_id() -> str:
    """Generate a hex ID (32 chars for trace_id, 16 for span_id)."""
    return uuid.uuid4().hex


@dataclass
class Span:
    """A single unit of work in a trace.

    Args:
        trace_id: The overall trace ID.
        span_id: Unique ID for this span.
        name: Span name (e.g. "HTTP GET /tools/add").
        start_time: Unix timestamp of start.
        end_time: Unix timestamp of end (None if still open).
        attributes: Arbitrary key-value metadata.
        parent_id: ID of the parent span (None for root).
        status: "ok", "error", or "unset".
    """

    trace_id: str
    span_id: str
    name: str
    start_time: float
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None
    status: str = "unset"

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 3),
            "attributes": self.attributes,
            "parent_id": self.parent_id,
            "status": self.status,
        }


@dataclass
class TraceContext:
    """Carries trace/space IDs for propagation.

    Can be serialized to HTTP headers for cross-service propagation.
    """

    trace_id: str
    span_id: str

    def to_headers(self) -> dict[str, str]:
        """Convert to W3C TraceContext-style headers."""
        return {
            "traceparent": f"00-{self.trace_id}-{self.span_id}-01",
        }

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> TraceContext | None:
        """Parse from W3C traceparent header."""
        traceparent = headers.get("traceparent", "")
        parts = traceparent.split("-")
        if len(parts) == 4 and len(parts[1]) == 32:
            return cls(trace_id=parts[1], span_id=parts[2])
        return None


class Tracer:
    """Collects spans and provides trace queries.

    Args:
        service_name: Name of this service (for span attribution).
        max_spans: Maximum number of spans to retain (FIFO).
    """

    def __init__(self, service_name: str = "api", max_spans: int = 10000) -> None:
        self.service_name = service_name
        self.max_spans = max_spans
        self._spans: list[Span] = []
        self._open_spans: dict[str, Span] = {}

    def start_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_id: str | None = None,
        **attributes: Any,
    ) -> Span:
        """Start a new span.

        Args:
            name: Span name.
            trace_id: Inherit trace ID (or create new).
            parent_id: Parent span ID.
            **attributes: Span attributes.

        Returns:
            The new Span (still open).
        """
        if trace_id is None:
            trace_id = _gen_id()
        span = Span(
            trace_id=trace_id,
            span_id=_gen_id(),
            name=name,
            start_time=time.time(),
            attributes={"service": self.service_name, **attributes},
            parent_id=parent_id,
        )
        self._open_spans[span.span_id] = span
        return span

    def end_span(self, span: Span, *, status: str = "ok") -> Span:
        """End an open span.

        Args:
            span: The span to close.
            status: Final status ("ok" or "error").

        Returns:
            The same span (now closed).
        """
        span.end_time = time.time()
        span.status = status
        self._open_spans.pop(span.span_id, None)
        self._append(span)
        return span

    def _append(self, span: Span) -> None:
        self._spans.append(span)
        if len(self._spans) > self.max_spans:
            del self._spans[: len(self._spans) - self.max_spans]

    def get_traces(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get completed traces (grouped by trace_id, most recent first).

        Args:
            limit: Max number of traces to return.

        Returns:
            List of trace dicts: {trace_id, spans: [...]}
        """
        traces: dict[str, list[dict[str, Any]]] = {}
        for span in reversed(self._spans):
            if span.end_time is None:
                continue
            traces.setdefault(span.trace_id, []).append(span.to_dict())
            if len(traces) >= limit:
                break
        return [
            {"trace_id": tid, "spans": spans, "span_count": len(spans)}
            for tid, spans in traces.items()
        ]

    def get_span(self, span_id: str) -> Span | None:
        """Get a specific span by ID."""
        for s in self._spans:
            if s.span_id == span_id:
                return s
        return None

    def clear(self) -> None:
        """Clear all collected spans."""
        self._spans.clear()
        self._open_spans.clear()

    def __len__(self) -> int:
        return len(self._spans)


def enable_tracing(app: FastAPI, tracer: Tracer | None = None) -> Tracer:
    """Install tracing middleware + /traces endpoint.

    Args:
        app: The FastAPI application.
        tracer: Optional existing Tracer.

    Returns:
        The Tracer in use.
    """
    tracer = tracer or Tracer()

    @app.get("/traces", include_in_schema=False)
    async def traces_endpoint(limit: int = 20) -> Response:
        """Return recent traces as JSON."""
        data = tracer.get_traces(limit=min(limit, 100))
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
        )

    @app.middleware("http")
    async def tracing_middleware(request: Request, call_next):
        """Create a span for every request."""
        # Try to continue an existing trace from headers
        ctx = TraceContext.from_headers(dict(request.headers))
        trace_id = ctx.trace_id if ctx else None
        parent_id = ctx.span_id if ctx else None

        span = tracer.start_span(
            f"{request.method} {request.url.path}",
            trace_id=trace_id,
            parent_id=parent_id,
            method=request.method,
            path=str(request.url.path),
            query=str(request.url.query),
        )
        # Set the new span context on the response
        span_ctx = TraceContext(trace_id=span.trace_id, span_id=span.span_id)

        try:
            response = await call_next(request)
            tracer.end_span(span, status="ok")
        except Exception:
            tracer.end_span(span, status="error")
            raise

        # Add trace context to response headers
        for k, v in span_ctx.to_headers().items():
            response.headers[k] = v
        return response

    return tracer
