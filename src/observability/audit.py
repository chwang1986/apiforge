"""ApiForge audit log.

Records "who did what when" for security/compliance.

Each audit entry captures:
    - timestamp
    - actor (user / API key / anonymous)
    - action (tool name)
    - resource (path)
    - result (success / error + status)
    - metadata (extra fields)

Entries are stored in-memory (ring buffer) and can be queried
or exported as JSON.

Usage:
    from src.observability.audit import AuditLog, enable_audit

    audit = AuditLog(max_entries=10000)
    enable_audit(app, audit)

    # In your tool handler or middleware:
    audit.record(
        actor="alice",
        action="delete_user",
        resource="/tools/delete_user",
        result="success",
        metadata={"user_id": 42},
    )

    # Query:
    entries = audit.query(actor="alice", action="delete_user")
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request, Response


@dataclass
class AuditEntry:
    """A single audit log entry.

    Args:
        timestamp: Unix timestamp.
        actor: Who performed the action (user, API key name, "anonymous").
        action: What was done (tool name or operation).
        resource: Target resource path.
        result: "success", "error", or "denied".
        status_code: HTTP status code (0 if N/A).
        metadata: Arbitrary extra data.
        ip_address: Client IP (optional).
    """

    timestamp: float = field(default_factory=time.time)
    actor: str = "anonymous"
    action: str = ""
    resource: str = ""
    result: str = "success"
    status_code: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "result": self.result,
            "status_code": self.status_code,
            "metadata": self.metadata,
            "ip_address": self.ip_address,
        }

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class AuditLog:
    """In-memory audit log with query capabilities.

    Args:
        max_entries: Maximum entries to retain (FIFO ring buffer).
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self.max_entries = max_entries
        self._entries: list[AuditEntry] = []
        self._lock = threading.Lock()

    def record(
        self,
        *,
        actor: str = "anonymous",
        action: str = "",
        resource: str = "",
        result: str = "success",
        status_code: int = 0,
        metadata: dict[str, Any] | None = None,
        ip_address: str = "",
    ) -> AuditEntry:
        """Record an audit event.

        Args:
            actor: Who performed the action.
            action: What was done.
            resource: Target resource.
            result: "success", "error", or "denied".
            status_code: HTTP status code.
            metadata: Extra data.
            ip_address: Client IP.

        Returns:
            The created AuditEntry.
        """
        entry = AuditEntry(
            actor=actor,
            action=action,
            resource=resource,
            result=result,
            status_code=status_code,
            metadata=metadata or {},
            ip_address=ip_address,
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self.max_entries:
                del self._entries[: len(self._entries) - self.max_entries]
        return entry

    def query(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        resource: str | None = None,
        result: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query audit entries with filters.

        Args:
            actor: Filter by actor.
            action: Filter by action.
            resource: Filter by resource.
            result: Filter by result.
            since: Only entries after this timestamp.
            until: Only entries before this timestamp.
            limit: Max entries to return.

        Returns:
            List of matching AuditEntry objects (newest first).
        """
        results: list[AuditEntry] = []
        with self._lock:
            for entry in reversed(self._entries):
                if actor and entry.actor != actor:
                    continue
                if action and entry.action != action:
                    continue
                if resource and entry.resource != resource:
                    continue
                if result and entry.result != result:
                    continue
                if since is not None and entry.timestamp < since:
                    continue
                if until is not None and entry.timestamp > until:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._entries.clear()

    def export_json(self) -> str:
        """Export all entries as a JSON array string."""
        with self._lock:
            return json.dumps(
                [e.to_dict() for e in self._entries],
                ensure_ascii=False,
                indent=2,
                default=str,
            )

    def summary(self) -> dict[str, Any]:
        """Get a summary of the audit log.

        Returns:
            Dict with total, by_result, by_actor, by_action counts.
        """
        with self._lock:
            total = len(self._entries)
            by_result: dict[str, int] = {}
            by_actor: dict[str, int] = {}
            by_action: dict[str, int] = {}
            for e in self._entries:
                by_result[e.result] = by_result.get(e.result, 0) + 1
                by_actor[e.actor] = by_actor.get(e.actor, 0) + 1
                by_action[e.action] = by_action.get(e.action, 0) + 1
            return {
                "total": total,
                "by_result": by_result,
                "by_actor": by_actor,
                "by_action": by_action,
            }

    def __len__(self) -> int:
        return len(self._entries)


def enable_audit(
    app: FastAPI,
    audit: AuditLog | None = None,
) -> AuditLog:
    """Install audit middleware + /audit endpoint.

    Args:
        app: The FastAPI application.
        audit: Optional existing AuditLog.

    Returns:
        The AuditLog in use.
    """
    audit = audit or AuditLog()

    @app.get("/audit", include_in_schema=False)
    async def audit_endpoint(
        actor: str = "",
        action: str = "",
        limit: int = 50,
    ) -> Response:
        """Query audit log entries."""
        entries = audit.query(
            actor=actor or None,
            action=action or None,
            limit=min(limit, 500),
        )
        return Response(
            content=json.dumps([e.to_dict() for e in entries], indent=2, default=str),
            media_type="application/json",
        )

    @app.get("/audit/summary", include_in_schema=False)
    async def audit_summary() -> Response:
        """Get audit log summary."""
        return Response(
            content=json.dumps(audit.summary(), indent=2),
            media_type="application/json",
        )

    @app.middleware("http")
    async def audit_middleware(request: Request, call_next):
        """Record every request in the audit log."""
        ip = request.client.host if request.client else ""
        actor = request.headers.get("X-Actor", "anonymous")

        response = await call_next(request)

        result = "success" if response.status_code < 400 else "error"
        audit.record(
            actor=actor,
            action=request.url.path,
            resource=request.url.path,
            result=result,
            status_code=response.status_code,
            ip_address=ip,
            metadata={"method": request.method},
        )
        return response

    return audit
