"""Round 43: JSON structured logging tests."""

import io
import json
import logging
import pytest

from fastapi.testclient import TestClient

from src.server import ApiForge
from src.observability.logging import (
    JsonFormatter,
    LogContext,
    log_context,
    get_context,
    setup_json_logging,
    enable_json_request_logging,
    parse_json_logs,
)


# --- JsonFormatter ---

def test_json_formatter_basic() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="x.py", lineno=1,
        msg="hello world", args=(), exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["message"] == "hello world"
    assert data["logger"] == "test"
    assert "timestamp" in data


def test_json_formatter_extra_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="x.py", lineno=1,
        msg="with extras", args=(), exc_info=None,
    )
    record.custom_key = "custom_value"
    record.num = 42
    data = json.loads(formatter.format(record))
    assert data["custom_key"] == "custom_value"
    assert data["num"] == 42


def test_json_formatter_exception() -> None:
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = __import__("sys").exc_info()
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="x.py", lineno=1,
        msg="error occurred", args=(), exc_info=exc_info,
    )
    data = json.loads(formatter.format(record))
    assert "exception" in data
    assert "ValueError" in data["exception"]


# --- LogContext ---

def test_log_context_merges_fields() -> None:
    formatter = JsonFormatter()
    with log_context(user="alice", region="eu"):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="x.py", lineno=1,
            msg="contextual", args=(), exc_info=None,
        )
        data = json.loads(formatter.format(record))
    assert data["user"] == "alice"
    assert data["region"] == "eu"


def test_log_context_nested() -> None:
    formatter = JsonFormatter()
    with log_context(a=1):
        with log_context(b=2):
            record = logging.LogRecord(
                name="t", level=logging.INFO, pathname="x", lineno=1,
                msg="nested", args=(), exc_info=None,
            )
            data = json.loads(formatter.format(record))
        assert data["a"] == 1
        assert data["b"] == 2
    # After context exits, fields gone
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname="x", lineno=1,
        msg="after", args=(), exc_info=None,
    )
    data = json.loads(formatter.format(record))
    assert "a" not in data
    assert "b" not in data


def test_get_context() -> None:
    assert get_context() == {}
    with log_context(x=99):
        assert get_context()["x"] == 99


def test_log_context_reset_on_error() -> None:
    formatter = JsonFormatter()
    with pytest.raises(RuntimeError):
        with log_context(should_gone=True):
            raise RuntimeError("fail")
    # After error, context reset
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname="x", lineno=1,
        msg="check", args=(), exc_info=None,
    )
    data = json.loads(formatter.format(record))
    assert "should_gone" not in data


# --- setup_json_logging ---

def test_setup_json_logging_captures() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("r43_test")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    logger.info("captured message", extra={"key": "val"})
    output = stream.getvalue()
    lines = [l for l in output.strip().splitlines() if l]
    assert len(lines) >= 1
    data = json.loads(lines[0])
    assert data["message"] == "captured message"
    assert data["key"] == "val"

    logger.handlers.clear()


# --- parse_json_logs ---

def test_parse_json_logs() -> None:
    raw = json.dumps({"a": 1}) + "\n" + json.dumps({"b": 2}) + "\n"
    raw += "not json\n"
    raw += "\n"
    entries = parse_json_logs(raw)
    assert len(entries) == 2
    assert entries[0] == {"a": 1}
    assert entries[1] == {"b": 2}


def test_parse_json_logs_empty() -> None:
    assert parse_json_logs("") == []
    assert parse_json_logs("\n\n") == []


# --- enable_json_request_logging integration ---

def test_json_request_logging_integration() -> None:
    import contextlib

    f = ApiForge(name="JsonLog")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    logger = enable_json_request_logging(f.app)

    # Capture log output
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    c = TestClient(f.app)
    c.post("/tools/add", json={"a": 1, "b": 2})

    logger.removeHandler(handler)
    output = stream.getvalue()
    entries = parse_json_logs(output)
    assert len(entries) >= 1
    req_log = next(e for e in entries if e.get("message") == "request")
    assert req_log["status"] == 200
    assert "duration_ms" in req_log
    assert req_log["method"] == "POST"
    assert req_log["path"] == "/tools/add"


def test_json_request_logging_error_status() -> None:
    from src.errors import ToolError

    f = ApiForge(name="JsonLogErr")

    @f.tool
    def fail() -> str:
        """Fail."""
        raise ToolError("bad", status_code=400)

    logger = enable_json_request_logging(f.app)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    c = TestClient(f.app)
    c.post("/tools/fail", json={})

    logger.removeHandler(handler)
    entries = parse_json_logs(stream.getvalue())
    req_log = next(e for e in entries if e.get("message") == "request")
    assert req_log["status"] == 400
