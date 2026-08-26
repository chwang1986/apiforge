"""Round 10: Request logging middleware tests."""

import logging
import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.middleware.logging import request_logger


@pytest.fixture
def forge() -> ApiForge:
    """ApiForge with request logging enabled."""
    f = ApiForge(name="LogTest", log_requests=True)

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    return f


@pytest.fixture
def client(forge: ApiForge) -> TestClient:
    return TestClient(forge.app, raise_server_exceptions=False)


# --- Basic functionality ---

def test_logging_does_not_break_requests(client: TestClient) -> None:
    """Requests still work normally with logging enabled."""
    resp = client.post("/tools/ping", json={})
    assert resp.status_code == 200
    assert resp.json() == "pong"


def test_response_time_header_present(client: TestClient) -> None:
    """X-Response-Time header is added by the middleware."""
    resp = client.post("/tools/ping", json={})
    assert "x-response-time" in resp.headers
    assert resp.headers["x-response-time"].endswith("ms")


def test_health_is_skipped(client: TestClient) -> None:
    """Health check is not logged (skipped by middleware)."""
    # Health should still work, just not logged
    resp = client.get("/health")
    assert resp.status_code == 200


# --- Log capture ---

def test_log_output_captured(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """Request log entries are written to the apiforge.requests logger."""
    with caplog.at_level(logging.INFO, logger="apiforge.requests"):
        client.post("/tools/ping", json={})

    # Find our log entry (LogRecord uses .name, not .logger)
    log_messages = [r.getMessage() for r in caplog.records if r.name == "apiforge.requests"]
    assert len(log_messages) >= 1
    # Should contain method, path, status
    entry = log_messages[0]
    assert "POST" in entry
    assert "/tools/ping" in entry
    assert "200" in entry


def test_log_contains_elapsed(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """Log entry includes elapsed time."""
    with caplog.at_level(logging.INFO, logger="apiforge.requests"):
        client.post("/tools/ping", json={})

    log_messages = [r.getMessage() for r in caplog.records if r.name == "apiforge.requests"]
    assert len(log_messages) >= 1
    assert "ms" in log_messages[0]


# --- Without logging ---

def test_no_logging_by_default() -> None:
    """Without log_requests=True, no X-Response-Time header."""
    f = ApiForge(name="NoLog")

    @f.tool
    def hello() -> str:
        """Say hello."""
        return "hello"

    c = TestClient(f.app)
    resp = c.post("/tools/hello", json={})
    assert resp.status_code == 200
    # No X-Response-Time header (middleware not added)
    assert "x-response-time" not in resp.headers
