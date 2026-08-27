"""Round 33: forge CLI tests."""

import json
import os
import tempfile
import pytest

from forge_cli import build_parser, main


def _write_spec(tmp: str) -> str:
    """Write a minimal OpenAPI spec and return its path."""
    spec = {
        "info": {"title": "TestAPI", "version": "1.0"},
        "paths": {
            "/tools/echo": {
                "post": {
                    "operationId": "echo",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"properties": {"msg": {"type": "string"}}}
                            }
                        }
                    },
                }
            }
        },
    }
    path = os.path.join(tmp, "spec.json")
    with open(path, "w") as f:
        json.dump(spec, f)
    return path


# --- build_parser ---

def test_parser_requires_command() -> None:
    """Parser has subcommands."""
    parser = build_parser()
    # No command → error (required=True)
    import argparse
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_subcommands() -> None:
    """Each subcommand parses."""
    parser = build_parser()
    args = parser.parse_args(["version"])
    assert args.command == "version"

    with pytest.raises(SystemExit):
        parser.parse_args(["client"])  # missing required --spec


# --- version ---

def test_cmd_version() -> None:
    """version command returns 0."""
    rc = main(["version"])
    assert rc == 0


# --- init ---

def test_cmd_init_creates_files() -> None:
    """init creates project skeleton."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "proj")
        rc = main(["init", "--name", "MySvc", "--out", out])
        assert rc == 0
        assert os.path.exists(os.path.join(out, "main.py"))
        assert os.path.exists(os.path.join(out, "pyproject.toml"))
        assert os.path.exists(os.path.join(out, "src", "__init__.py"))
        # main.py mentions the service name
        with open(os.path.join(out, "main.py")) as f:
            content = f.read()
        assert "MySvc" in content
        assert "ApiForge" in content


# --- client ---

def test_cmd_client_stdout() -> None:
    """client generates code to stdout."""
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = _write_spec(tmp)
        rc = main(["client", "--spec", spec_path, "--name", "MyClient"])
        assert rc == 0


def test_cmd_client_out_file() -> None:
    """client writes to file."""
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = _write_spec(tmp)
        out_file = os.path.join(tmp, "client.py")
        rc = main(["client", "--spec", spec_path, "--out", out_file])
        assert rc == 0
        assert os.path.exists(out_file)
        with open(out_file) as f:
            content = f.read()
        assert "class Client:" in content or "Client" in content
        # valid python
        compile(content, "<gen>", "exec")


# --- curl ---

def test_cmd_curl() -> None:
    """curl generates commands."""
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = _write_spec(tmp)
        rc = main(["curl", "--spec", spec_path])
        assert rc == 0


# --- openapi ---

def test_cmd_openapi() -> None:
    """openapi prints spec."""
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = _write_spec(tmp)
        rc = main(["openapi", "--spec", spec_path])
        assert rc == 0


# --- missing spec ---

def test_cmd_client_missing_spec() -> None:
    """Missing spec file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        main(["client", "--spec", "/nonexistent/spec.json"])
