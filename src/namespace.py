"""ApiForge namespaces.

Group related tools under a shared URL prefix and OpenAPI tag.

Usage:
    forge = ApiForge(name="MyService")
    users = forge.namespace("users")

    @users.tool
    def get(id: int) -> dict:
        '''Get a user.'''
        return {"id": id}

    # Route: /users/get  (prefix "users" applied)
    # OpenAPI tag: "users"

    # Nested namespaces:
    admin = forge.namespace("admin")
    audit = admin.namespace("audit")

    @audit.tool
    def logs() -> list:
        return []

    # Route: /admin/audit/logs
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI


class Namespace:
    """A namespaced grouping of tools under a URL prefix.

    Args:
        app: The FastAPI application (shared with parent forge).
        prefix: URL prefix (e.g. "users" → routes under /users/).
        parent: Parent Namespace (for nesting).
        tag: OpenAPI tag (defaults to full path).
    """

    def __init__(
        self,
        app: FastAPI,
        prefix: str,
        parent: "Namespace | None" = None,
        tag: str | None = None,
    ) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/")
        self.parent = parent
        self.tag = tag or self._full_prefix()

    def _full_prefix(self) -> str:
        """Compute the full prefix chain (e.g. admin/audit)."""
        parts = []
        ns: Namespace | None = self
        while ns is not None:
            parts.append(ns.prefix)
            ns = ns.parent
        return "/".join(reversed(parts))

    def full_path(self, name: str) -> str:
        """Full route path for a tool in this namespace."""
        return f"/{self._full_prefix()}/{name}"

    def tool(
        self,
        func: Callable | None = None,
        *,
        method: str = "POST",
        path: str | None = None,
    ) -> Callable:
        """Register a tool under this namespace.

        Same as forge.tool but with the namespace prefix applied.
        """
        # Reuse the ApiForge.tool machinery by delegating to a helper
        # that uses the same handler-building logic.
        from src.server import ApiForge

        # We need access to the ApiForge instance to reuse tool() logic.
        # The Namespace stores a reference set by forge.namespace().
        forge: ApiForge = self._forge  # type: ignore[attr-defined]

        def register(f: Callable) -> Callable:
            tool_name = f.__name__
            base = path or self.full_path(tool_name)

            # Delegate to the parent forge's tool registration with
            # the namespaced path and an extra tag.
            forge._register_tool(
                f,
                method=method,
                path=base,
                extra_tags=[self.tag],
            )
            return f

        if func is not None:
            return register(func)
        return register

    def namespace(self, name: str) -> "Namespace":
        """Create a nested namespace."""
        ns = Namespace(self.app, name, parent=self, tag=None)
        ns._forge = self._forge  # type: ignore[attr-defined]
        return ns
