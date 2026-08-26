"""ApiForge unified response envelope.

Wraps successful tool responses in a consistent structure:

    {
        "status": "ok",
        "data": <tool result>,
        "meta": {
            "tool": "add",
            "request_id": "abc-123"
        }
    }

Error responses (from errors.py) use:

    {
        "error": {
            "code": "...",
            "message": "...",
            "tool": "...",
            "request_id": "..."
        }
    }
"""

from __future__ import annotations

import time
import uuid
from typing import Any


def wrap_response(
    data: Any,
    tool: str | None = None,
    request_id: str | None = None,
    elapsed_ms: float | None = None,
) -> dict[str, Any]:
    """Wrap a successful tool result in the standard envelope.

    Args:
        data: The raw return value from the tool function.
        tool: Name of the tool (for meta).
        request_id: Correlation/request ID.
        elapsed_ms: Processing time in milliseconds.

    Returns:
        The wrapped response dict.
    """
    meta: dict[str, Any] = {}
    if tool:
        meta["tool"] = tool
    if request_id:
        meta["request_id"] = request_id
    if elapsed_ms is not None:
        meta["elapsed_ms"] = round(elapsed_ms, 2)

    return {
        "status": "ok",
        "data": data,
        "meta": meta,
    }


def generate_request_id() -> str:
    """Generate a short unique request ID."""
    return uuid.uuid4().hex[:12]


def measure_start() -> float:
    """Get a timestamp for measuring elapsed time."""
    return time.perf_counter()


def elapsed_ms(start: float) -> float:
    """Calculate elapsed milliseconds from a start timestamp."""
    return (time.perf_counter() - start) * 1000
