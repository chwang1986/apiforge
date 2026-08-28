"""Round 46: Docker support tests.

Validates Dockerfile, .dockerignore, and docker-compose.yml
are present and well-formed (no actual docker build in tests).
"""

import os
import pytest
import yaml  # type: ignore


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    full = os.path.join(REPO, path)
    assert os.path.exists(full), f"Missing file: {path}"
    with open(full, "r", encoding="utf-8") as f:
        return f.read()


# --- Dockerfile ---

def test_dockerfile_exists() -> None:
    content = _read("Dockerfile")
    assert "FROM python:3.11-slim" in content


def test_dockerfile_exposes_port() -> None:
    content = _read("Dockerfile")
    assert "EXPOSE 8000" in content


def test_dockerfile_has_healthcheck() -> None:
    content = _read("Dockerfile")
    assert "HEALTHCHECK" in content
    assert "/health" in content


def test_dockerfile_non_root() -> None:
    content = _read("Dockerfile")
    assert "USER 1000" in content


def test_dockerfile_installs_deps() -> None:
    content = _read("Dockerfile")
    assert "fastapi" in content
    assert "uvicorn" in content


def test_dockerfile_has_cmd() -> None:
    content = _read("Dockerfile")
    assert "CMD" in content
    assert "uvicorn" in content


# --- .dockerignore ---

def test_dockerignore_exists() -> None:
    content = _read(".dockerignore")
    assert "git" in content
    assert "__pycache__" in content


def test_dockerignore_excludes_tests() -> None:
    content = _read(".dockerignore")
    assert "tests/" in content


# --- docker-compose.yml ---

def test_compose_yaml_valid() -> None:
    content = _read("docker-compose.yml")
    data = yaml.safe_load(content)
    assert "services" in data
    assert "api" in data["services"]


def test_compose_api_service() -> None:
    content = _read("docker-compose.yml")
    data = yaml.safe_load(content)
    api = data["services"]["api"]
    assert "build" in api
    assert "ports" in api
    assert "healthcheck" in api


def test_compose_ports() -> None:
    content = _read("docker-compose.yml")
    data = yaml.safe_load(content)
    api = data["services"]["api"]
    ports = api["ports"]
    assert any("8000" in str(p) for p in ports)
