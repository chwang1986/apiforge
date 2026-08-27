"""Python client SDK generator.

Generates a typed Python client from an OpenAPI spec.

Usage:
    from src.codegen.client import generate_client

    spec = app.openapi()
    code = generate_client(spec, client_name="MyClient")
    # code is a Python source string
"""

from __future__ import annotations

import re
from typing import Any


def _type_hint(schema: dict[str, Any]) -> str:
    """Map OpenAPI schema type to Python type hint."""
    t = schema.get("type", "string")
    mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list[Any]",
        "object": "dict[str, Any]",
    }
    return mapping.get(t, "Any")


def _build_method_name(op: dict[str, Any], path: str, seen: set[str]) -> str:
    """Derive a unique method name for a tool endpoint."""
    name = op.get("operationId") or ""
    if not name:
        name = path.strip("/").replace("/", "_").replace("{", "get_").replace("}", "")
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = name.strip("_") or "call"
    base = name
    counter = 2
    while name in seen:
        name = f"{base}_{counter}"
        counter += 1
    seen.add(name)
    return name


def generate_client_code(spec: dict[str, Any], client_name: str = "Client") -> str:
    """Generate a Python client class from an OpenAPI spec.

    Args:
        spec: The OpenAPI 3.x dict (from app.openapi()).
        client_name: Name of the generated client class.

    Returns:
        Python source code as a string.
    """
    title = spec.get("info", {}).get("title", "API")
    lines: list[str] = []

    # Header
    lines.append(f'"""Auto-generated {client_name} for {title}."""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from typing import Any")
    lines.append("")
    lines.append("import httpx")
    lines.append("")
    lines.append("")
    lines.append(f"class {client_name}:")
    lines.append(f'    """HTTP client for {title}."""')
    lines.append("")
    lines.append("    def __init__(self, base_url: str = \"http://localhost:8000\", api_key: str | None = None) -> None:")
    lines.append("        self.base_url = base_url.rstrip('/')")
    lines.append("        self.api_key = api_key")
    lines.append("")

    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    seen_names: set[str] = set()

    for path, operations in paths.items():
        for method, op in operations.items():
            if method not in http_methods:
                continue
            # Skip system endpoints
            if any(skip in path for skip in ("health", "openapi", "docs", "redoc")):
                continue

            name = _build_method_name(op, path, seen_names)
            doc = (op.get("summary") or op.get("description") or name).strip().split("\n")[0]

            # Collect path params
            path_params = re.findall(r"\{(\w+)\}", path)

            # Collect body params from schema
            body_schema = (
                op.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )
            props = body_schema.get("properties", {})
            body_params = list(props.keys())

            # Build signature
            sig_parts: list[str] = [f"{p}: Any" for p in path_params]
            sig_parts += [f"{bp}: {_type_hint(props[bp])}" for bp in body_params]
            sig = ", ".join(sig_parts)
            if sig:
                sig += ", "
            sig += "**kwargs: Any"

            # Build URL expression
            if path_params:
                fmt_args = ", ".join(f"{p}={p}" for p in path_params)
                url_line = f'        url = self.base_url + "{path}".format({fmt_args})'
            else:
                url_line = f'        url = self.base_url + "{path}"'

            lines.append(f"    def {name}(self, {sig}) -> dict[str, Any]:")
            lines.append(f'        """{doc}"""')
            lines.append(url_line)

            # Build body
            if body_params:
                lines.append("        body: dict[str, Any] = {}")
                for bp in body_params:
                    lines.append(f"        if {bp} is not None:")
                    lines.append(f"            body[{bp!r}] = {bp}")
            else:
                lines.append("        body = None")

            # Headers
            lines.append("        headers: dict[str, str] = {}")
            lines.append("        if self.api_key:")
            lines.append('            headers["Authorization"] = f"Bearer {self.api_key}"')
            lines.append("        headers.update(kwargs.pop('headers', {}))")

            # Request
            lines.append(f"        resp = httpx.request({method.upper()!r}, url, json=body, headers=headers, **kwargs)")
            lines.append("        resp.raise_for_status()")
            lines.append("        return resp.json()")
            lines.append("")

    return "\n".join(lines)


def generate_client(
    app_or_spec: Any,
    client_name: str = "Client",
) -> str:
    """Convenience: generate client from a FastAPI app or spec dict.

    Args:
        app_or_spec: A FastAPI app instance or OpenAPI spec dict.
        client_name: Name of the generated class.

    Returns:
        Python source code.
    """
    if isinstance(app_or_spec, dict):
        spec = app_or_spec
    else:
        spec = app_or_spec.openapi()
    return generate_client_code(spec, client_name=client_name)
