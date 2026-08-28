"""Round 48: PyPI publishing flow tests.

Validates pyproject.toml has proper PyPI metadata and Makefile
has all required release targets.
"""

import os
import tomllib
import pytest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_pyproject() -> dict:
    path = os.path.join(REPO, "pyproject.toml")
    assert os.path.exists(path), "Missing pyproject.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)


def _read_makefile() -> str:
    path = os.path.join(REPO, "Makefile")
    assert os.path.exists(path), "Missing Makefile"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# --- pyproject.toml ---

def test_pyproject_has_name() -> None:
    data = _load_pyproject()
    assert data["project"]["name"] == "apiforge"


def test_pyproject_has_version() -> None:
    data = _load_pyproject()
    assert data["project"]["version"] == "0.1.0"


def test_pyproject_has_license() -> None:
    data = _load_pyproject()
    assert "license" in data["project"]


def test_pyproject_has_authors() -> None:
    data = _load_pyproject()
    authors = data["project"].get("authors", [])
    assert len(authors) >= 1
    assert "name" in authors[0]


def test_pyproject_has_urls() -> None:
    data = _load_pyproject()
    urls = data["project"].get("urls", {})
    assert "Homepage" in urls
    assert "Repository" in urls


def test_pyproject_has_classifiers() -> None:
    data = _load_pyproject()
    classifiers = data["project"].get("classifiers", [])
    assert len(classifiers) >= 3
    assert any("Python" in c for c in classifiers)


def test_pyproject_has_keywords() -> None:
    data = _load_pyproject()
    keywords = data["project"].get("keywords", [])
    assert len(keywords) >= 2


def test_pyproject_has_readme() -> None:
    data = _load_pyproject()
    assert "readme" in data["project"]


def test_pyproject_build_system() -> None:
    data = _load_pyproject()
    assert "build-system" in data
    assert "hatchling" in data["build-system"]["requires"]


# --- Makefile ---

def test_makefile_exists() -> None:
    content = _read_makefile()
    assert "help" in content


def test_makefile_has_test_target() -> None:
    content = _read_makefile()
    assert "test:" in content
    assert "pytest" in content


def test_makefile_has_build_target() -> None:
    content = _read_makefile()
    assert "build:" in content
    assert "python -m build" in content or "-m build" in content


def test_makefile_has_publish_target() -> None:
    content = _read_makefile()
    assert "publish:" in content
    assert "twine" in content


def test_makefile_has_clean_target() -> None:
    content = _read_makefile()
    assert "clean:" in content
    assert "dist" in content


def test_makefile_has_publish_test_target() -> None:
    content = _read_makefile()
    assert "publish-test:" in content
    assert "testpypi" in content
