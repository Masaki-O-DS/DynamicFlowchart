"""Command line interface for CodeFlow Viewer."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from codeflow import __version__

DEFAULT_CONFIG = """# CodeFlow Viewer configuration
schema_version: 1
project:
  name: ""
scanner:
  include:
    - "**/*.py"
  exclude_dirs:
    - test
    - tests
    - __pycache__
    - venv
    - .venv
    - .git
    - node_modules
  exclude_files:
    - "test_*.py"
    - "*_test.py"
    - ".env"
    - "*.pem"
    - "*.key"
    - "*.crt"
    - ".streamlit/secrets.toml"
ai:
  default_model: "GLM-5"
  auto_fallback: false
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codeflow",
        description="Create code understanding assets for Python and Streamlit projects.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")
    init_parser = subparsers.add_parser(
        "init",
        help="Create a starter codeflow.yaml in the target project.",
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project directory to initialize. Defaults to the current directory.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing codeflow.yaml.",
    )
    init_parser.set_defaults(func=run_init)

    return parser


def run_init(args: argparse.Namespace) -> int:
    target_dir = Path(args.path).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    config_path = target_dir / "codeflow.yaml"

    if config_path.exists() and not args.force:
        print(f"codeflow.yaml already exists: {config_path}")
        print("Use --force to overwrite it.")
        return 1

    config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    print(f"Created {config_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return int(args.func(args))
