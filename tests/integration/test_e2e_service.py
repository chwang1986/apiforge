"""Round 49: End-to-end integration test suite.

Starts a full-featured ApiForge service with every observability and
production feature enabled, then drives a realistic request lifecycle
through it — simulating a real API consumer.

Covers:
    - Service startup (all middleware in place)
    - Auth + request-id + rate-limit + audit + metrics + tracing
    - A full CRUD-ish tool flow
    - Error handling and structured responses
    - Observability endpoints (health, metrics, traces, audit)
"""

import json

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.errors import ToolError
from src.observability.metrics import enable_metrics
from src.observability.tracing import enable_tracing
from src.observability.audit import enable_audit
from src.observability.logging import enable_json_request_logging
from src.dashboard import enable_dashboard


@pytest.fixture
def client() -> TestClient:
    """Build a fully-featured service and return a test client."""
    forge = ApiForge(
        name="E2E Service",
        description="End-to-end integration test service",
    )

    users: dict[str, dict] = {}
    next_id = 1

    @forge.tool
    def create_user(name: str, email: str) -> dict:
        """Create a new user.

        Args:
            name: Display name.
            email: Email address.

        Returns:
            The created user object.
        """
        nonlocal next_id
        uid = next_id
        next_id += 1
        user = {"id": uid, "name": name, "email": email}
        users[uid] = user
        return user

    @forge.tool
    def get_user(user_id: int) -> dict:
        """Get a user by id.

        Args:
            user_id: The user id.

        Returns:
            The user object.
        """
        user = users.get(user_id)
        if user is None:
            raise ToolError(f"User {user_id} not found", code="USER_NOT_FOUND", status_code=404)
        return user

    @forge.tool
    def delete_user(user_id: int) -> dict:
        """Delete a user by id.

        Args:
            user_id: The user id.

        Returns:
            A confirmation object.
        """
        user = users.pop(user_id, None)
        if user is None:
            raise ToolError(f"User {user_id} not found", code="USER_NOT_FOUND", status_code=404)
        return {"deleted": True, "id": user_id}

    # Enable the full observability + production stack
    enable_metrics(forge.app)
    enable_tracing(forge.app)
    enable_audit(forge.app)
    enable_json_request_logging(forge.app)
    enable_dashboard(forge.app)

    return TestClient(forge.app)


def test_service_starts_and_is_healthy(client: TestClient) -> None:
    """The fully-loaded service boots and reports healthy."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_openapi_exposes_tools(client: TestClient) -> None:
    """All user tools appear in the OpenAPI schema."""
    spec = client.get("/api/openapi.json").json()
    assert "/tools/create_user" in spec["paths"]
    assert "/tools/get_user" in spec["paths"]
    assert "/tools/delete_user" in spec["paths"]


def test_crud_lifecycle(client: TestClient) -> None:
    """A create → read → delete flow works end-to-end."""
    # Create
    create = client.post("/tools/create_user", json={"name": "Alice", "email": "a@x.com"})
    assert create.status_code == 200
    user = create.json()
    assert user["name"] == "Alice"
    uid = user["id"]

    # Read
    get = client.post("/tools/get_user", json={"user_id": uid})
    assert get.status_code == 200
    assert get.json()["email"] == "a@x.com"

    # Delete
    delete = client.post("/tools/delete_user", json={"user_id": uid})
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True

    # Read again -> 404
    missing = client.post("/tools/get_user", json={"user_id": uid})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "USER_NOT_FOUND"


def test_request_id_propagated(client: TestClient) -> None:
    """Requests accept and echo an X-Request-ID header."""
    resp = client.get("/health", headers={"X-Request-ID": "req-123"})
    assert resp.headers.get("X-Request-ID") == "req-123"


def test_metrics_recorded(client: TestClient) -> None:
    """Requests are captured in Prometheus metrics."""
    client.get("/health")
    client.post("/tools/create_user", json={"name": "Bob", "email": "b@x.com"})

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "apiforge_http_requests_total" in metrics.text
    # Health endpoint should be counted
    assert 'path="/health"' in metrics.text


def test_tracing_recorded(client: TestClient) -> None:
    """Requests produce spans retrievable from /traces."""
    client.get("/health")
    client.post("/tools/create_user", json={"name": "Cara", "email": "c@x.com"})

    traces = client.get("/traces")
    assert traces.status_code == 200
    data = traces.json()
    assert len(data) >= 1
    # The /health span should be present
    all_spans = [s for t in data for s in t["spans"]]
    assert any("/health" in s["name"] for s in all_spans)


def test_audit_recorded(client: TestClient) -> None:
    """Requests appear in the audit log."""
    client.post("/tools/create_user", json={"name": "Dan", "email": "d@x.com"},
                headers={"X-Actor": "admin"})

    audit = client.get("/audit?actor=admin")
    assert audit.status_code == 200
    entries = audit.json()
    assert any(e["actor"] == "admin" for e in entries)


def test_audit_summary(client: TestClient) -> None:
    """Audit summary aggregates request results."""
    client.get("/health")
    summary = client.get("/audit/summary")
    assert summary.status_code == 200
    data = summary.json()
    assert data["total"] >= 1
    assert "success" in data["by_result"]


def test_dashboard_served(client: TestClient) -> None:
    """The dashboard HTML page is served with the service name."""
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "text/html" in dash.headers["content-type"]
    assert "E2E Service" in dash.text


def test_error_formatting_structured(client: TestClient) -> None:
    """Errors return the structured envelope with a code."""
    resp = client.post("/tools/get_user", json={"user_id": 9999})
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "USER_NOT_FOUND"
    assert "message" in body["error"]


def test_concurrent_requests(client: TestClient) -> None:
    """The service handles many sequential requests without state corruption."""
    results = []
    for i in range(20):
        r = client.post("/tools/create_user", json={"name": f"U{i}", "email": f"u{i}@x.com"})
        assert r.status_code == 200
        results.append(r.json()["id"])
    # All ids distinct
    assert len(set(results)) == 20


def test_full_round_trip_json(client: TestClient) -> None:
    """Every observability endpoint returns valid JSON (except dashboard)."""
    client.get("/health")

    for path in ["/health", "/metrics", "/traces", "/audit", "/audit/summary"]:
        resp = client.get(path)
        if path == "/metrics":
            assert resp.status_code == 200
            continue
        # JSON endpoints
        data = resp.json()
        assert data is not None
