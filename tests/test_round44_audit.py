"""Round 44: Audit log tests."""

import json
import time
import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.observability.audit import AuditEntry, AuditLog, enable_audit


# --- AuditEntry ---

def test_audit_entry_fields() -> None:
    e = AuditEntry(
        actor="alice",
        action="delete_user",
        resource="/tools/delete_user",
        result="success",
        status_code=200,
        metadata={"user_id": 42},
        ip_address="10.0.0.1",
    )
    assert e.actor == "alice"
    assert e.action == "delete_user"
    assert e.timestamp > 0


def test_audit_entry_to_dict() -> None:
    e = AuditEntry(actor="bob", action="read", resource="/api/data", result="success")
    d = e.to_dict()
    assert d["actor"] == "bob"
    assert d["action"] == "read"
    assert d["status_code"] == 0
    assert d["metadata"] == {}


def test_audit_entry_to_json() -> None:
    e = AuditEntry(actor="carol", action="write")
    s = e.to_json()
    parsed = json.loads(s)
    assert parsed["actor"] == "carol"


# --- AuditLog ---

def test_record_entry() -> None:
    log = AuditLog(max_entries=100)
    entry = log.record(actor="alice", action="create", resource="/tools/create")
    assert isinstance(entry, AuditEntry)
    assert len(log) == 1
    assert entry.actor == "alice"


def test_query_by_actor() -> None:
    log = AuditLog()
    log.record(actor="alice", action="read", resource="/a")
    log.record(actor="bob", action="write", resource="/b")

    results = log.query(actor="alice")
    assert len(results) == 1
    assert results[0].actor == "alice"


def test_query_by_action() -> None:
    log = AuditLog()
    log.record(actor="alice", action="create", resource="/x")
    log.record(actor="alice", action="delete", resource="/y")

    results = log.query(action="delete")
    assert len(results) == 1
    assert results[0].action == "delete"


def test_query_by_result() -> None:
    log = AuditLog()
    log.record(actor="alice", action="ok", result="success")
    log.record(actor="alice", action="fail", result="error")

    errors = log.query(result="error")
    assert len(errors) == 1
    assert errors[0].action == "fail"


def test_query_since_until() -> None:
    log = AuditLog()
    log.record(actor="a", action="old")
    time.sleep(0.01)
    log.record(actor="a", action="new")

    now = time.time()
    results = log.query(since=now - 0.005)
    assert len(results) == 1
    assert results[0].action == "new"


def test_query_limit() -> None:
    log = AuditLog()
    for i in range(10):
        log.record(actor="x", action=f"op_{i}")

    results = log.query(limit=3)
    assert len(results) == 3


def test_max_entries_fiffo() -> None:
    log = AuditLog(max_entries=5)
    for i in range(10):
        log.record(actor="x", action=f"op_{i}")
    assert len(log) == 5
    # Should have the last 5 (op_5 through op_9)
    results = log.query(limit=10)
    assert results[0].action == "op_9"  # newest first


def test_clear() -> None:
    log = AuditLog()
    log.record(actor="a", action="x")
    assert len(log) == 1
    log.clear()
    assert len(log) == 0


def test_export_json() -> None:
    log = AuditLog()
    log.record(actor="alice", action="create", result="success")
    log.record(actor="bob", action="delete", result="error")
    data = json.loads(log.export_json())
    assert len(data) == 2
    assert data[0]["actor"] == "alice"


def test_summary() -> None:
    log = AuditLog()
    log.record(actor="alice", action="read", result="success")
    log.record(actor="alice", action="write", result="success")
    log.record(actor="bob", action="delete", result="error")

    s = log.summary()
    assert s["total"] == 3
    assert s["by_result"]["success"] == 2
    assert s["by_result"]["error"] == 1
    assert s["by_actor"]["alice"] == 2
    assert s["by_actor"]["bob"] == 1


# --- enable_audit integration ---

def test_audit_endpoint() -> None:
    f = ApiForge(name="Audit")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    audit = enable_audit(f.app)
    c = TestClient(f.app)

    # Make a request
    c.post("/tools/add", json={"a": 1, "b": 2})

    # Check /audit
    resp = c.get("/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["actor"] == "anonymous"


def test_audit_summary_endpoint() -> None:
    f = ApiForge(name="AuditSum")

    @f.tool
    def ping() -> str:
        """Ping."""
        return "pong"

    enable_audit(f.app)
    c = TestClient(f.app)

    c.post("/tools/ping", json={})
    resp = c.get("/audit/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_audit_actor_header() -> None:
    f = ApiForge(name="AuditActor")

    @f.tool
    def secret() -> str:
        """Secret."""
        return "data"

    audit = enable_audit(f.app)
    c = TestClient(f.app)

    c.post("/tools/secret", json={}, headers={"X-Actor": "admin"})
    results = audit.query(actor="admin")
    assert len(results) == 1
