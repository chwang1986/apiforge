"""Round 30: OpenAPI enhancement tests."""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge


# --- Summary in OpenAPI ---

def test_summary_in_openapi() -> None:
    """Tool with summary appears in OpenAPI spec."""
    f = ApiForge(name="OpenAPI")

    @f.tool(summary="Add two numbers together")
    def add(a: int, b: int) -> int:
        """Add numbers."""
        return a + b

    c = TestClient(f.app)
    spec = c.get("/api/openapi.json").json()
    op = spec["paths"]["/tools/add"]["post"]
    assert op["summary"] == "Add two numbers together"


def test_description_defaults_to_doc() -> None:
    """Without summary, description comes from docstring."""
    f = ApiForge(name="Doc")

    @f.tool
    def greet(name: str) -> str:
        """Greet a person by name."""
        return f"Hi, {name}"

    c = TestClient(f.app)
    spec = c.get("/api/openapi.json").json()
    op = spec["paths"]["/tools/greet"]["post"]
    assert op["description"] == "Greet a person by name."


# --- Examples in OpenAPI ---

def test_examples_in_openapi() -> None:
    """Examples appear in OpenAPI spec."""
    f = ApiForge(name="Examples")

    @f.tool(
        summary="Multiply numbers",
        examples={"default": {"value": {"a": 3, "b": 7}}},
    )
    def multiply(a: int, b: int) -> int:
        """Multiply."""
        return a * b

    c = TestClient(f.app)
    spec = c.get("/api/openapi.json").json()
    op = spec["paths"]["/tools/multiply"]["post"]
    # openapi_extra merges into operation
    assert "requestBody" in op
    assert op["requestBody"]["examples"]["default"]["value"] == {"a": 3, "b": 7}


def test_multiple_examples() -> None:
    """Multiple named examples work."""
    f = ApiForge(name="MultiEx")

    @f.tool(
        examples={
            "small": {"value": {"a": 1, "b": 2}},
            "large": {"value": {"a": 100, "b": 200}},
        },
    )
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    c = TestClient(f.app)
    spec = c.get("/api/openapi.json").json()
    examples = spec["paths"]["/tools/add"]["post"]["requestBody"]["examples"]
    assert "small" in examples
    assert "large" in examples
    assert examples["large"]["value"]["b"] == 200


# --- Tool still works functionally ---

def test_tool_with_summary_still_works() -> None:
    """Summary/examples don't affect runtime behavior."""
    f = ApiForge(name="Functional")

    @f.tool(summary="Sum", examples={"ex": {"value": {"x": 5}}})
    def compute(x: int) -> int:
        """Compute."""
        return x * 10

    c = TestClient(f.app)
    resp = c.post("/tools/compute", json={"x": 5})
    assert resp.status_code == 200
    assert resp.json() == 50


# --- Without examples, no requestBody extra ---

def test_no_examples_no_requestbody_extra() -> None:
    """Tools without examples don't have injected examples."""
    f = ApiForge(name="NoEx")

    @f.tool
    def simple(x: int) -> int:
        """Simple."""
        return x

    c = TestClient(f.app)
    spec = c.get("/api/openapi.json").json()
    op = spec["paths"]["/tools/simple"]["post"]
    # openapi_extra was not set, so no injected examples
    if "requestBody" in op:
        assert "examples" not in op.get("requestBody", {})
