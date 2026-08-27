"""cURL command generator.

Generates cURL commands for each tool endpoint from an OpenAPI spec.

Usage:
    from src.codegen.curl import generate_curl_commands

    spec = app.openapi()
    commands = generate_curl_commands(spec, base_url="http://localhost:8000")
"""

from __future__ import annotations

import json
import re
from typing import Any


def _resolve_ref(schema: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Resolve a $ref pointer in the spec."""
    if "$ref" not in schema:
        return schema
    ref = schema["$ref"]  # e.g. "#/components/schemas/AddRequest"
    parts = ref.lstrip("#/").split("/")
    node: Any = spec
    for part in parts:
        node = node.get(part, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, dict) else {}


def _get_props(op: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Extract request body properties (resolving $ref)."""
    schema = (
        op.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    schema = _resolve_ref(schema, spec)
    return schema.get("properties", {})


def _build_example_body(props: dict[str, Any]) -> dict[str, Any]:
    """Build an example body from schema properties."""
    result: dict[str, Any] = {}
    for name, schema in props.items():
        t = schema.get("type", "string")
        if t == "string":
            result[name] = "example"
        elif t == "integer":
            result[name] = 1
        elif t == "number":
            result[name] = 1.0
        elif t == "boolean":
            result[name] = True
        elif t == "array":
            result[name] = []
        elif t == "object":
            result[name] = {}
        else:
            result[name] = None
    return result


def generate_curl_for_operation(
    method: str,
    path: str,
    op: dict[str, Any],
    base_url: str = "http://localhost:8000",
    api_key: str | None = None,
    spec: dict[str, Any] | None = None,
) -> str:
    """Generate a cURL command for a single OpenAPI operation."""
    if spec is None:
        spec = {}
    url = base_url.rstrip("/") + path

    # Path params: replace {param} with <param>
    path_params = re.findall(r"\{(\w+)\}", path)
    for p in path_params:
        url = url.replace(f"{{{p}}}", f"<{p}>")

    parts: list[str] = [f"curl -X {method.upper()}", f"'{url}'"]

    # Headers
    parts.append("-H 'Content-Type: application/json'")
    if api_key:
        parts.append(f"-H 'Authorization: Bearer {api_key}'")

    # Body
    props = _get_props(op, spec)
    examples = op.get("requestBody", {}).get("examples")

    body: str | None = None
    if examples:
        first_key = next(iter(examples))
        body = json.dumps(examples[first_key].get("value", {}))
    elif props:
        body = json.dumps(_build_example_body(props))

    if body and method.upper() != "GET":
        parts.append(f"-d '{body}'")

    return " \\\n  ".join(parts)


def generate_curl_commands(
    spec: dict[str, Any],
    base_url: str = "http://localhost:8000",
    api_key: str | None = None,
) -> dict[str, str]:
    """Generate cURL commands for all tool endpoints."""
    commands: dict[str, str] = {}
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}

    for path, operations in paths.items():
        for method, op in operations.items():
            if method not in http_methods:
                continue
            if any(skip in path for skip in ("health", "openapi", "docs", "redoc")):
                continue
            name = op.get("operationId") or path.strip("/").replace("/", "_")
            commands[name] = generate_curl_for_operation(
                method, path, op, base_url=base_url, api_key=api_key, spec=spec
            )

    return commands


def generate_curl(
    app_or_spec: Any,
    base_url: str = "http://localhost:8000",
    api_key: str | None = None,
) -> dict[str, str]:
    """Convenience: generate cURL commands from a FastAPI app or spec dict."""
    if isinstance(app_or_spec, dict):
        spec = app_or_spec
    else:
        spec = app_or_spec.openapi()
    return generate_curl_commands(spec, base_url=base_url, api_key=api_key)
