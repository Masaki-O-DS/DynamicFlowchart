"""Project file scanner for CodeFlow Viewer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import fnmatch
import json
import os
from pathlib import Path

from codeflow import __version__
from codeflow.config import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_FILES,
    SCHEMA_VERSION,
)


@dataclass(frozen=True)
class ScanRules:
    exclude_dirs: tuple[str, ...] = DEFAULT_EXCLUDE_DIRS
    exclude_files: tuple[str, ...] = DEFAULT_EXCLUDE_FILES


class ProjectScanner:
    """Collect Python files and record excluded paths with reasons."""

    def __init__(self, rules: ScanRules | None = None) -> None:
        self.rules = rules or ScanRules()

    def scan(self, project_path: Path) -> dict[str, object]:
        root = project_path.expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Project path does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Project path is not a directory: {root}")

        included_files: list[dict[str, object]] = []
        excluded_paths: list[dict[str, object]] = []

        for current_dir, dir_names, file_names in os.walk(root, topdown=True):
            current_path = Path(current_dir)
            dir_names.sort()
            file_names.sort()

            kept_dirs = []
            for dir_name in dir_names:
                dir_path = current_path / dir_name
                relative_path = self._relative_posix(root, dir_path)
                if dir_name in self.rules.exclude_dirs:
                    excluded_paths.append(
                        {
                            "path": relative_path,
                            "kind": "directory",
                            "reason": "excluded_directory",
                            "rule": dir_name,
                        }
                    )
                    continue
                kept_dirs.append(dir_name)
            dir_names[:] = kept_dirs

            for file_name in file_names:
                file_path = current_path / file_name
                relative_path = self._relative_posix(root, file_path)
                file_rule = self._matching_file_rule(relative_path, file_name)
                if file_rule is not None:
                    excluded_paths.append(
                        self._excluded_file(relative_path, "excluded_file_pattern", file_rule)
                    )
                    continue

                if file_path.suffix != ".py":
                    excluded_paths.append(
                        self._excluded_file(relative_path, "not_python_file", "*.py")
                    )
                    continue

                included_files.append(self._included_file(root, file_path))

        return {
            "schema_version": SCHEMA_VERSION,
            "codeflow_version": __version__,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_root": str(root),
            "rules": {
                "include_files": ["**/*.py"],
                "exclude_dirs": list(self.rules.exclude_dirs),
                "exclude_files": list(self.rules.exclude_files),
            },
            "summary": {
                "included_file_count": len(included_files),
                "excluded_path_count": len(excluded_paths),
            },
            "included_files": included_files,
            "excluded_paths": excluded_paths,
        }

    def write_project_index(self, project_path: Path, output_path: Path | None = None) -> Path:
        root = project_path.expanduser().resolve()
        index = self.scan(root)
        destination = output_path or (root / ".codeflow" / "project_index.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination

    def _matching_file_rule(self, relative_path: str, file_name: str) -> str | None:
        for pattern in self.rules.exclude_files:
            target = relative_path if "/" in pattern else file_name
            if fnmatch.fnmatch(target, pattern):
                return pattern
        return None

    def _included_file(self, root: Path, file_path: Path) -> dict[str, object]:
        stat = file_path.stat()
        return {
            "path": self._relative_posix(root, file_path),
            "kind": "file",
            "reason": "included_python_file",
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }

    @staticmethod
    def _excluded_file(relative_path: str, reason: str, rule: str) -> dict[str, object]:
        return {
            "path": relative_path,
            "kind": "file",
            "reason": reason,
            "rule": rule,
        }

    @staticmethod
    def _relative_posix(root: Path, path: Path) -> str:
        return path.relative_to(root).as_posix()


def scan_project(project_path: Path, output_path: Path | None = None) -> Path:
    return ProjectScanner().write_project_index(project_path, output_path)
