"""Command line interface for CodeFlow Viewer."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from codeflow import __version__
from codeflow.config import DEFAULT_CONFIG
from codeflow.scanner import ProjectScanner


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

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a project and write .codeflow/project_index.json.",
    )
    scan_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project directory to scan. Defaults to the current directory.",
    )
    scan_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional project_index.json output path.",
    )
    scan_parser.set_defaults(func=run_scan)

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


def run_scan(args: argparse.Namespace) -> int:
    output_path = Path(args.output).expanduser().resolve() if args.output else None
    index_path = ProjectScanner().write_project_index(Path(args.path), output_path)
    print(f"Created {index_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return int(args.func(args))
