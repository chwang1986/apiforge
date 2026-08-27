"""Round 12: Rate limiting middleware tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.middleware.rate_limit import TokenBucket


@pytest.fixture
def forge_rl() -> ApiForge:
    """ApiForge with strict rate limiting (5 requests per window)."""
    f = ApiForge(
        name="RateLimit Test",
        rate_limit={"requests": 5, "window_seconds": 60},
    )

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    return f


@pytest.fixture
def client(forge_rl: ApiForge) -> TestClient:
    return TestClient(forge_rl.app, raise_server_exceptions=False)


# --- TokenBucket unit tests ---

def test_token_bucket_initial_state() -> None:
    """New bucket is full."""
    bucket = TokenBucket(capacity=5, refill_rate=0.1)
    assert bucket.tokens == 5.0


def test_token_bucket_consume() -> None:
    """Consume reduces tokens."""
    bucket = TokenBucket(capacity=5, refill_rate=0.0)  # no refill
    for _ in range(5):
        assert bucket.consume() is True
    assert bucket.consume() is False


def test_token_bucket_retry_after() -> None:
    """retry_after returns reasonable value when empty."""
    bucket = TokenBucket(capacity=2, refill_rate=1.0)  # 1 token/sec
    bucket.consume()
    bucket.consume()
    assert bucket.consume() is False
    assert bucket.retry_after_seconds > 0


# --- Integration: within limit ---

def test_within_limit(client: TestClient) -> None:
    """First 5 requests succeed."""
    for i in range(5):
        resp = client.post("/tools/ping", json={})
        assert resp.status_code == 200, f"Request {i+1} should succeed"


def test_rate_limit_headers_present(client: TestClient) -> None:
    """Successful responses include X-RateLimit headers."""
    resp = client.post("/tools/ping", json={})
    assert resp.status_code == 200
    assert "x-ratelimit-limit" in resp.headers
    assert "x-ratelimit-remaining" in resp.headers
    assert resp.headers["x-ratelimit-limit"] == "5"


# --- Integration: exceeding limit ---

def test_exceed_limit_returns_429() -> None:
    """6th request returns 429."""
    f = ApiForge(name="RL", rate_limit={"requests": 3, "window_seconds": 60})

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app, raise_server_exceptions=False)

    # Use up 3 tokens
    for _ in range(3):
        resp = c.post("/tools/ping", json={})
        assert resp.status_code == 200

    # 4th should be rate limited
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 429
    data = resp.json()
    assert data["error"]["code"] == "RATE_LIMITED"
    assert "retry_after" in data["error"]


def test_429_has_retry_after_header() -> None:
    """429 response includes Retry-After header."""
    f = ApiForge(name="RL2", rate_limit={"requests": 2, "window_seconds": 60})

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app, raise_server_exceptions=False)
    c.post("/tools/ping", json={})
    c.post("/tools/ping", json={})
    resp = c.post("/tools/ping", json={})
    assert resp.status_code == 429
    assert "retry-after" in resp.headers


# --- Health check is exempt ---

def test_health_exempt_from_rate_limit() -> None:
    """Health check is never rate limited."""
    f = ApiForge(name="RL3", rate_limit={"requests": 1, "window_seconds": 60})

    @f.tool
    def ping() -> str:
        """Return pong."""
        return "pong"

    c = TestClient(f.app, raise_server_exceptions=False)
    # Use up the 1 token
    c.post("/tools/ping", json={})
    # Health check still works
    resp = c.get("/health")
    assert resp.status_code == 200


# --- No rate limit (default) ---

def test_no_rate_limit_by_default() -> None:
    """Without rate_limit, no X-RateLimit headers."""
    f = ApiForge(name="NoRL")

    @f.tool
    def hello() -> str:
        """Say hi."""
        return "hi"

    c = TestClient(f.app)
    resp = c.post("/tools/hello", json={})
    assert "x-ratelimit-limit" not in resp.headers
