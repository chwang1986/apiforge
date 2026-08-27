"""ApiForge CLI.

A lightweight command-line interface built on the standard library
(argparse) so it has no extra dependencies.

Subcommands:
    forge init --name MyService   Create a new project skeleton.
    forge client --spec SPEC      Generate a Python client (from spec JSON file).
    forge curl --spec SPEC        Generate cURL commands (from spec JSON file).
    forge openapi --spec SPEC     Print the OpenAPI spec.
    forge version                 Print version info.

Usage examples:
    python forge_cli.py version
    python forge_cli.py init --name MyService --out ./my_service
    python forge_cli.py curl --spec openapi.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from typing import Any


# --- init -----------------------------------------------------------------

INIT_MAIN_TEMPLATE = '''"""ApiForge service entrypoint."""

from src.server import ApiForge

forge = ApiForge(name="{name}")


@forge.tool
def echo(message: str) -> str:
    """Echo the input message back."""
    return message


if __name__ == "__main__":
    forge.run(host="0.0.0.0", port=8000)
'''


def _cmd_init(args: argparse.Namespace) -> int:
    """Create a new project skeleton."""
    out_dir = os.path.abspath(args.out)
    src_dir = os.path.join(out_dir, "src")
    os.makedirs(src_dir, exist_ok=True)

    # __init__.py
    init_py = os.path.join(src_dir, "__init__.py")
    if not os.path.exists(init_py):
        with open(init_py, "w", encoding="utf-8") as f:
            f.write('"""{name} service package."""\n'.format(name=args.name))

    # main.py
    main_py = os.path.join(out_dir, "main.py")
    if not os.path.exists(main_py):
        with open(main_py, "w", encoding="utf-8") as f:
            f.write(INIT_MAIN_TEMPLATE.format(name=args.name))

    # pyproject.toml
    pyproject = os.path.join(out_dir, "pyproject.toml")
    if not os.path.exists(pyproject):
        with open(pyproject, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(f'''\
                [project]
                name = "{args.name.lower()}"
                version = "0.1.0"
                dependencies = [
                    "fastapi>=0.110",
                    "uvicorn>=0.29",
                ]
            '''))

    print(f"Created project skeleton at {out_dir}")
    print(f"  - {os.path.join(out_dir, 'main.py')}")
    print(f"  - {os.path.join(out_dir, 'pyproject.toml')}")
    print(f"  - {os.path.join(src_dir, '__init__.py')}")
    return 0


# --- spec loading ----------------------------------------------------------

def _load_spec(path: str) -> dict[str, Any]:
    """Load an OpenAPI spec from a JSON file or URL string."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError(f"Spec file not found: {path}")


# --- client ----------------------------------------------------------------

def _cmd_client(args: argparse.Namespace) -> int:
    """Generate a Python client from a spec."""
    from src.codegen.client import generate_client_code

    spec = _load_spec(args.spec)
    code = generate_client_code(spec, client_name=args.name or "Client")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"Client written to {args.out}")
    else:
        print(code)
    return 0


# --- curl ------------------------------------------------------------------

def _cmd_curl(args: argparse.Namespace) -> int:
    """Generate cURL commands from a spec."""
    from src.codegen.curl import generate_curl_commands

    spec = _load_spec(args.spec)
    commands = generate_curl_commands(spec, base_url=args.base_url)
    for name, cmd in commands.items():
        print(f"# {name}")
        print(cmd)
        print()
    return 0


# --- openapi ---------------------------------------------------------------

def _cmd_openapi(args: argparse.Namespace) -> int:
    """Print the OpenAPI spec."""
    spec = _load_spec(args.spec)
    print(json.dumps(spec, indent=2, ensure_ascii=False))
    return 0


# --- version ---------------------------------------------------------------

def _cmd_version(args: argparse.Namespace) -> int:
    """Print version info."""
    try:
        from src._version import __version__
        version = __version__
    except Exception:
        version = "unknown"
    print(f"ApiForge {version}")
    print(f"Python {sys.version.split()[0]}")
    return 0


# --- parser ----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="forge",
        description="ApiForge CLI - build, test, and deploy API tool services.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Create a new project skeleton.")
    p_init.add_argument("--name", default="MyService", help="Service name.")
    p_init.add_argument("--out", default=".", help="Output directory.")
    p_init.set_defaults(func=_cmd_init)

    # client
    p_client = sub.add_parser("client", help="Generate a Python client from a spec.")
    p_client.add_argument("--spec", required=True, help="OpenAPI spec JSON file.")
    p_client.add_argument("--name", default=None, help="Client class name.")
    p_client.add_argument("--out", default=None, help="Output file (default: stdout).")
    p_client.set_defaults(func=_cmd_client)

    # curl
    p_curl = sub.add_parser("curl", help="Generate cURL commands from a spec.")
    p_curl.add_argument("--spec", required=True, help="OpenAPI spec JSON file.")
    p_curl.add_argument("--base-url", default="http://localhost:8000", help="Base URL.")
    p_curl.set_defaults(func=_cmd_curl)

    # openapi
    p_openapi = sub.add_parser("openapi", help="Print the OpenAPI spec.")
    p_openapi.add_argument("--spec", required=True, help="OpenAPI spec JSON file.")
    p_openapi.set_defaults(func=_cmd_openapi)

    # version
    p_version = sub.add_parser("version", help="Print version info.")
    p_version.set_defaults(func=_cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
