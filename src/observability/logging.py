"""Json structured logging for ApiForge.

Provides a stdlib `logging` formatter that emits each record as a
single-line JSON object, plus a context manager for adding temporary
context fields, and a FastAPI middleware for request-scoped fields.

No external dependencies (no structlog / python-json-logger).

Usage:
    from src.observability.logging import JsonFormatter, setup_json_logging, log_context

    setup_json_logging(level="INFO")

    with log_context(user="alice", region="us-east"):
        logging.getLogger("app").info("created resource")
    # -> {"timestamp": ..., "level": "INFO", "message": "created resource",
    #     "user": "alice", "region": "us-east"}
"""

from __future__ import annotations

import contextvars
import json
import logging
import time
from typing import Any

from fastapi import FastAPI, Request, Response


# Context field storage (per-request / per-task safe via contextvars)
_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "apiforge_log_context", default={}
)


class LogContext:
    """Context manager that merges extra fields into log records.

    Usage:
        with log_context(user="alice"):
            logger.info("hello")
    """

    def __init__(self, **extra: Any) -> None:
        self.extra = extra
        self.token: contextvars.Token | None = None

    def __enter__(self) -> "LogContext":
        current = dict(_context.get())
        current.update(self.extra)
        self.token = _context.set(current)
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.token is not None:
            _context.reset(self.token)


def log_context(**extra: Any) -> LogContext:
    """Create a context manager to add fields to all logs within a block."""
    return LogContext(**extra)


def get_context() -> dict[str, Any]:
    """Get the current log context fields."""
    return dict(_context.get())


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON.

    Args:
        include: Extra record attributes to always include (default: timestamp,
            level, logger, message).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge current context
        try:
            payload.update(_context.get())
        except Exception:
            pass

        # Merge per-record extras (fields not in the standard LogRecord set)
        standard = set(
            logging.makeLogRecord({}).__dict__
        )
        for key, value in record.__dict__.items():
            if key not in standard and not key.startswith("_"):
                payload[key] = value

        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_json_logging(
    level: str = "INFO",
    logger_name: str | None = None,
) -> logging.Handler:
    """Configure JSON logging for a logger (or root).

    Args:
        level: Minimum level (e.g. "DEBUG", "INFO").
        logger_name: Specific logger to attach to (None = root).

    Returns:
        The handler that was attached (for later removal in tests).
    """
    logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    # Avoid duplicate handlers on repeated calls
    for h in list(logger.handlers):
        if isinstance(h, logging.StreamHandler) and isinstance(h.formatter, JsonFormatter):
            logger.removeHandler(h)
    logger.addHandler(handler)
    return handler


class JsonRequestLogMiddleware:
    """ASGI middleware that logs every request as a JSON line.

    Records: method, path, status, duration_ms, client, request_id,
    and any fields set via log_context() during the request.
    """

    def __init__(self, app: Any, logger: logging.Logger | None = None) -> None:
        self.app = app
        self.logger = logger or logging.getLogger("apiforge.request")

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client", ("unknown", 0))[0]

        status_code: int = 500

        async def send_wrapper(message: Any) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                if "status" in message:
                    status_code = message["status"]
            await send(message)

        with LogContext(method=method, path=path, client=client):
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                duration_ms = (time.perf_counter() - start) * 1000
                self.logger.error("request failed", extra={
                    "status": 500,
                    "duration_ms": round(duration_ms, 2),
                })
                raise
            else:
                duration_ms = (time.perf_counter() - start) * 1000
                level = "error" if status_code >= 500 else (
                    "warning" if status_code >= 400 else "info"
                )
                getattr(self.logger, level)("request", extra={
                    "status": status_code,
                    "duration_ms": round(duration_ms, 2),
                })


def enable_json_request_logging(
    app: FastAPI,
    logger_name: str = "apiforge.request",
    level: str = "INFO",
) -> logging.Logger:
    """Enable JSON request logging middleware.

    Args:
        app: The FastAPI application.
        logger_name: Logger name for request logs.
        level: Log level.

    Returns:
        The logger configured for request logs.
    """
    setup_json_logging(level=level, logger_name=logger_name)
    logger = logging.getLogger(logger_name)
    app.add_middleware(JsonRequestLogMiddleware, logger=logger)
    return logger


def parse_json_logs(raw: str) -> list[dict[str, Any]]:
    """Parse a block of JSON-lines logs into a list of dicts.

    Args:
        raw: Raw log text (one JSON object per line).

    Returns:
        List of parsed log entries (skips invalid lines).
    """
    entries: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
