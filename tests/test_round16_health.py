"""Round 16: Dependency health checks tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.health import HealthRegistry, HealthCheckResult


# --- HealthRegistry unit tests ---

def test_registry_empty() -> None:
    """Empty registry has no checks."""
    reg = HealthRegistry()
    assert len(reg.checks) == 0


def test_registry_register() -> None:
    """Register adds a check."""
    reg = HealthRegistry()

    @reg.check("db")
    def check_db():
        pass

    assert len(reg.checks) == 1
    assert reg.checks[0].name == "db"


def test_registry_multiple() -> None:
    """Multiple checks registered."""
    reg = HealthRegistry()

    @reg.check("db")
    def check_db():
        pass

    @reg.check("redis")
    def check_redis():
        pass

    assert len(reg.checks) == 2
    names = [c.name for c in reg.checks]
    assert names == ["db", "redis"]


# --- HealthCheckResult ---

def test_result_healthy() -> None:
    """Healthy result serializes correctly."""
    r = HealthCheckResult(name="db", healthy=True, latency_ms=1.5)
    d = r.to_dict()
    assert d["name"] == "db"
    assert d["status"] == "ok"
    assert d["latency_ms"] == 1.5
    assert "error" not in d


def test_result_unhealthy() -> None:
    """Unhealthy result includes error."""
    r = HealthCheckResult(name="db", healthy=False, latency_ms=5000.0, error="connection refused")
    d = r.to_dict()
    assert d["status"] == "fail"
    assert d["error"] == "connection refused"


# --- Integration: all healthy ---

def test_health_detail_all_ok() -> None:
    """/health/detail returns ok when all checks pass."""
    f = ApiForge(name="AllOk")

    @f.health_check("db")
    def check_db():
        pass

    c = TestClient(f.app)
    resp = c.get("/health/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "checks" in data


def test_health_detail_with_passing_checks() -> None:
    """Registered passing checks appear in response."""
    f = ApiForge(name="HealthTest")

    @f.health_check("database")
    def check_db():
        """Simulate DB check."""
        pass

    @f.health_check("cache")
    async def check_cache():
        """Simulate cache check."""
        pass

    c = TestClient(f.app)
    resp = c.get("/health/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    check_names = [c["name"] for c in data["checks"]]
    assert "database" in check_names
    assert "cache" in check_names
    # All should be ok
    for check in data["checks"]:
        assert check["status"] == "ok"


# --- Integration: failing check ---

def test_health_detail_with_failing_check() -> None:
    """Failing check shows degraded status."""
    f = ApiForge(name="DegradedTest")

    @f.health_check("database")
    def check_db():
        """Simulate DB check (passing)."""
        pass

    @f.health_check("external_api")
    def check_api():
        """Simulate failing API check."""
        raise ConnectionError("timeout after 5s")

    c = TestClient(f.app)
    resp = c.get("/health/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    # Find the failing check
    failing = [c for c in data["checks"] if c["status"] == "fail"]
    assert len(failing) == 1
    assert failing[0]["name"] == "external_api"
    assert "timeout" in failing[0]["error"]


# --- Basic /health still works ---

def test_basic_health_still_works() -> None:
    """Original /health endpoint unaffected by health checks."""
    f = ApiForge(name="Basic")

    @f.health_check("db")
    def check_db():
        pass

    c = TestClient(f.app)
    resp = c.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "Basic"


# --- No registered checks ---

def test_health_detail_no_checks() -> None:
    """With no registered checks, still returns ok with empty list."""
    f = ApiForge(name="NoChecks")
    c = TestClient(f.app)
    resp = c.get("/health/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"] == []
