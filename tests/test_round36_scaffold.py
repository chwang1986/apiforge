"""Round 36: Project scaffolding tests."""

import os
import tempfile
import pytest
from src.codegen.scaffold import scaffold_project, scaffold_files


def test_scaffold_files_contents() -> None:
    """scaffold_files returns all expected paths."""
    files = scaffold_files("MySvc")
    expected = [
        "main.py",
        "pyproject.toml",
        "requirements.txt",
        "src/__init__.py",
        "tests/__init__.py",
        "tests/test_server.py",
        ".gitignore",
    ]
    for p in expected:
        assert p in files


def test_scaffold_files_name_in_main() -> None:
    """main.py contains the project name."""
    files = scaffold_files("CoolSvc")
    assert "CoolSvc" in files["main.py"]
    assert "ApiForge" in files["main.py"]


def test_scaffold_files_pyproject_name() -> None:
    """pyproject.toml contains lowercased name."""
    files = scaffold_files("My Service")
    assert "my-service" in files["pyproject.toml"]


def test_scaffold_files_test_template() -> None:
    """test_server.py is valid Python."""
    files = scaffold_files("T")
    compile(files["tests/test_server.py"], "<t>", "exec")


def test_scaffold_files_main_compiles() -> None:
    """main.py is valid Python."""
    files = scaffold_files("T")
    compile(files["main.py"], "<m>", "exec")


def test_scaffold_project_creates_files() -> None:
    """scaffold_project writes files to disk."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "proj")
        scaffold_project("MySvc", out_dir=out)

        assert os.path.exists(os.path.join(out, "main.py"))
        assert os.path.exists(os.path.join(out, "pyproject.toml"))
        assert os.path.exists(os.path.join(out, "requirements.txt"))
        assert os.path.exists(os.path.join(out, "src", "__init__.py"))
        assert os.path.exists(os.path.join(out, "tests", "test_server.py"))
        assert os.path.exists(os.path.join(out, ".gitignore"))


def test_scaffold_project_returns_dict() -> None:
    """scaffold_project returns the files dict."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "proj")
        files = scaffold_project("X", out_dir=out)
        assert isinstance(files, dict)
        assert "main.py" in files


def test_scaffold_idempotent() -> None:
    """Running scaffold twice doesn't crash (overwrites)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "proj")
        scaffold_project("A", out_dir=out)
        scaffold_project("A", out_dir=out)  # second run
        assert os.path.exists(os.path.join(out, "main.py"))
