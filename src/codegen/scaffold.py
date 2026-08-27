"""Project scaffolding generator.

Creates a full project structure from templates.

Usage:
    from src.codegen.scaffold import scaffold_project

    files = scaffold_project("MyService", out_dir="./my_service")
    # Creates:
    #   my_service/
    #   ├── main.py
    #   ├── pyproject.toml
    #   ├── requirements.txt
    #   ├── src/
    #   │   ├── __init__.py
    #   │   └── server.py
    #   └── tests/
    #       ├── __init__.py
    #       └── test_server.py
"""

from __future__ import annotations

import os
from typing import Any


MAIN_TEMPLATE = '''"""{name} service entrypoint."""

from src.server import ApiForge

forge = ApiForge(name="{name}")


@forge.tool
def echo(message: str) -> str:
    """Echo the input message back."""
    return message


if __name__ == "__main__":
    forge.run(host="0.0.0.0", port=8000)
'''

PYPROJECT_TEMPLATE = '''[project]
name = "{name_lower}"
version = "0.1.0"
description = "{name} - ApiForge service"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]
'''

REQUIREMENTS_TEMPLATE = '''fastapi>=0.110
uvicorn>=0.29
python-multipart>=0.0.9
'''

TEST_TEMPLATE = '''"""Tests for {name} service."""

import pytest
from fastapi.testclient import TestClient
from main import forge


@pytest.fixture
def client():
    return TestClient(forge.app)


def test_echo(client):
    resp = client.post("/tools/echo", json={{"message": "hello"}})
    assert resp.status_code == 200
    assert resp.json() == "hello"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
'''


def scaffold_project(name: str, out_dir: str = ".") -> dict[str, str]:
    """Create a project skeleton.

    Args:
        name: Project/service name.
        out_dir: Output directory.

    Returns:
        Dict mapping relative file paths to their content.
    """
    files: dict[str, str] = {
        "main.py": MAIN_TEMPLATE.format(name=name),
        "pyproject.toml": PYPROJECT_TEMPLATE.format(name=name, name_lower=name.lower().replace(" ", "-")),
        "requirements.txt": REQUIREMENTS_TEMPLATE,
        "src/__init__.py": f'"""{name} service package."""\n',
        "tests/__init__.py": "",
        "tests/test_server.py": TEST_TEMPLATE.format(name=name),
        ".gitignore": ".pytest_cache/\n__pycache__/\n*.pyc\n",
    }

    for rel_path, content in files.items():
        full_path = os.path.join(out_dir, rel_path)
        os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    return files


def scaffold_files(name: str = "MyService") -> dict[str, str]:
    """Generate scaffold file contents without writing to disk.

    Args:
        name: Project name.

    Returns:
        Dict mapping relative paths to file contents.
    """
    return {
        "main.py": MAIN_TEMPLATE.format(name=name),
        "pyproject.toml": PYPROJECT_TEMPLATE.format(name=name, name_lower=name.lower().replace(" ", "-")),
        "requirements.txt": REQUIREMENTS_TEMPLATE,
        "src/__init__.py": f'"""{name} service package."""\n',
        "tests/__init__.py": "",
        "tests/test_server.py": TEST_TEMPLATE.format(name=name),
        ".gitignore": ".pytest_cache/\n__pycache__/\n*.pyc\n",
    }
