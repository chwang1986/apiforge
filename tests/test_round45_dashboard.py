"""Round 45: Embedded dashboard tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.dashboard import enable_dashboard, get_dashboard_html


# --- get_dashboard_html ---

def test_dashboard_html_contains_service_name() -> None:
    html = get_dashboard_html("MyService", "1.0.0")
    assert "MyService" in html
    assert "1.0.0" in html


def test_dashboard_html_is_valid_html() -> None:
    html = get_dashboard_html("Test", "0.1")
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<head>" in html
    assert "<body>" in html


def test_dashboard_html_has_cards() -> None:
    html = get_dashboard_html("Dash")
    assert "Status" in html
    assert "Tools" in html
    assert "Requests" in html
    assert "Avg Latency" in html


def test_dashboard_html_has_tables() -> None:
    html = get_dashboard_html("T")
    assert "tools-table" in html
    assert "metrics-table" in html


def test_dashboard_html_has_javascript() -> None:
    html = get_dashboard_html("JS")
    assert "<script>" in html
    assert "fetch" in html
    assert "openapi.json" in html


def test_dashboard_html_has_css() -> None:
    html = get_dashboard_html("CSS")
    assert "<style>" in html
    assert "grid" in html


# --- enable_dashboard integration ---

def test_dashboard_endpoint() -> None:
    f = ApiForge(name="DashSvc")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    enable_dashboard(f.app)
    c = TestClient(f.app)

    resp = c.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "DashSvc" in resp.text


def test_dashboard_default_name() -> None:
    f = ApiForge(name="Default")
    enable_dashboard(f.app)
    c = TestClient(f.app)

    resp = c.get("/dashboard")
    assert "Default" in resp.text


def test_dashboard_custom_name() -> None:
    f = ApiForge(name="Original")
    enable_dashboard(f.app, service_name="Custom Name")
    c = TestClient(f.app)

    resp = c.get("/dashboard")
    assert "Custom Name" in resp.text


def test_dashboard_not_in_openapi() -> None:
    """Dashboard is hidden from OpenAPI schema."""
    f = ApiForge(name="Hidden")
    enable_dashboard(f.app)
    c = TestClient(f.app)

    spec = c.get("/api/openapi.json").json()
    assert "/dashboard" not in spec["paths"]


def test_dashboard_coexists_with_tools() -> None:
    """Dashboard works alongside tools."""
    f = ApiForge(name="Coexist")

    @f.tool
    def echo(msg: str) -> str:
        """Echo."""
        return msg

    enable_dashboard(f.app)
    c = TestClient(f.app)

    # Tool works
    assert c.post("/tools/echo", json={"msg": "hi"}).json() == "hi"
    # Dashboard works
    assert c.get("/dashboard").status_code == 200
    # Health works
    assert c.get("/health").status_code == 200
