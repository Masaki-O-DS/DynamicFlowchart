"""Streamlit-specific static analyzer."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from codeflow import __version__
from codeflow.config import SCHEMA_VERSION
from codeflow.scanner import ProjectScanner


STREAMLIT_DISPLAY_APIS = {
    "st.set_page_config",
    "st.title",
    "st.header",
    "st.subheader",
    "st.markdown",
    "st.write",
    "st.sidebar",
    "st.dataframe",
    "st.table",
    "st.metric",
    "st.plotly_chart",
    "st.download_button",
}

STREAMLIT_INPUT_APIS = {
    "st.text_input",
    "st.number_input",
    "st.selectbox",
    "st.multiselect",
    "st.date_input",
    "st.file_uploader",
    "st.button",
    "st.form",
    "st.form_submit_button",
}

STREAMLIT_STATE_CONTROL_APIS = {
    "st.session_state",
    "st.cache_data",
    "st.cache_resource",
    "st.rerun",
    "st.stop",
}

STREAMLIT_LAYOUT_APIS = {
    "st.tabs",
    "st.columns",
    "st.expander",
}

STREAMLIT_APIS = (
    STREAMLIT_DISPLAY_APIS
    | STREAMLIT_INPUT_APIS
    | STREAMLIT_STATE_CONTROL_APIS
    | STREAMLIT_LAYOUT_APIS
)


@dataclass(frozen=True)
class StreamlitSource:
    path: Path
    relative_path: str


class StreamlitAnalyzer:
    """Extract Streamlit APIs, state usage, callbacks, and entrypoint metadata."""

    def analyze(self, project_path: Path, entry: str | None = None) -> dict[str, object]:
        root = project_path.expanduser().resolve()
        project_index = ProjectScanner().scan(root)
        source_files = [
            StreamlitSource(root / str(item["path"]), str(item["path"]))
            for item in project_index["included_files"]
        ]
        config_entry = self._read_config_entrypoint(root)

        file_indexes: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []
        for source_file in source_files:
            try:
                file_indexes.append(self._analyze_file(source_file))
            except SyntaxError as error:
                errors.append(
                    {
                        "file": source_file.relative_path,
                        "error_type": "SyntaxError",
                        "message": error.msg,
                        "line": error.lineno,
                        "offset": error.offset,
                    }
                )
            except OSError as error:
                errors.append(
                    {
                        "file": source_file.relative_path,
                        "error_type": error.__class__.__name__,
                        "message": str(error),
                    }
                )

        entrypoint = self._select_entrypoint(root, file_indexes, entry, config_entry)
        pages = sorted(item["file"] for item in file_indexes if str(item["file"]).startswith("pages/"))
        streamlit_files = [item for item in file_indexes if int(item["streamlit_api_count"]) > 0]

        return {
            "schema_version": SCHEMA_VERSION,
            "codeflow_version": __version__,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_root": str(root),
            "entrypoint": entrypoint,
            "summary": {
                "file_count": len(source_files),
                "analyzed_file_count": len(file_indexes),
                "streamlit_file_count": len(streamlit_files),
                "page_count": len(pages),
                "error_count": len(errors),
            },
            "files": file_indexes,
            "pages": pages,
            "errors": errors,
        }

    def write_streamlit_index(
        self,
        project_path: Path,
        entry: str | None = None,
        output_path: Path | None = None,
    ) -> Path:
        root = project_path.expanduser().resolve()
        index = self.analyze(root, entry)
        destination = output_path or (root / ".codeflow" / "streamlit_index.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination

    def _analyze_file(self, source_file: StreamlitSource) -> dict[str, object]:
        source = source_file.path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=source_file.relative_path)
        collector = StreamlitCollector()
        collector.visit(tree)
        apis = sorted(collector.streamlit_apis, key=lambda item: (item["line"], item["api"]))
        callbacks = sorted(collector.callbacks, key=lambda item: (item["line"], item["callback_type"]))
        session_state = sorted(
            collector.session_state,
            key=lambda item: (item["line"], item["access"], str(item["key"])),
        )

        return {
            "file": source_file.relative_path,
            "streamlit_api_count": len(apis),
            "streamlit_apis": apis,
            "session_state": session_state,
            "callbacks": callbacks,
            "caches": sorted(collector.caches, key=lambda item: (item["line"], item["api"])),
            "control_flow": sorted(collector.control_flow, key=lambda item: (item["line"], item["api"])),
            "has_set_page_config": any(item["api"] == "st.set_page_config" for item in apis),
        }

    def _select_entrypoint(
        self,
        root: Path,
        file_indexes: list[dict[str, object]],
        cli_entry: str | None,
        config_entry: str | None,
    ) -> dict[str, object]:
        files_by_path = {str(item["file"]): item for item in file_indexes}

        if cli_entry:
            normalized = self._normalize_entry(root, cli_entry)
            return {"path": normalized, "source": "cli", "reason": "--entry"}

        if config_entry:
            normalized = self._normalize_entry(root, config_entry)
            return {"path": normalized, "source": "config", "reason": "project.entrypoint"}

        for candidate in ("streamlit_app.py", "app.py", "main.py"):
            if candidate in files_by_path:
                return {"path": candidate, "source": "auto", "reason": candidate}

        page_files = sorted(path for path in files_by_path if path.startswith("pages/"))
        if page_files:
            return {"path": page_files[0], "source": "auto", "reason": "pages/*.py"}

        page_config_files = [
            item for item in file_indexes if bool(item["has_set_page_config"])
        ]
        if page_config_files:
            return {
                "path": str(page_config_files[0]["file"]),
                "source": "auto",
                "reason": "st.set_page_config",
            }

        streamlit_files = [
            item for item in file_indexes if int(item["streamlit_api_count"]) > 0
        ]
        if streamlit_files:
            best = sorted(
                streamlit_files,
                key=lambda item: (-int(item["streamlit_api_count"]), str(item["file"])),
            )[0]
            return {
                "path": str(best["file"]),
                "source": "auto",
                "reason": "streamlit_api_count",
            }

        return {"path": None, "source": "auto", "reason": "not_found"}

    @staticmethod
    def _normalize_entry(root: Path, entry: str) -> str:
        entry_path = Path(entry).expanduser()
        if entry_path.is_absolute():
            try:
                return entry_path.resolve().relative_to(root).as_posix()
            except ValueError:
                return entry_path.as_posix()
        return entry_path.as_posix()

    @staticmethod
    def _read_config_entrypoint(root: Path) -> str | None:
        config_path = root / "codeflow.yaml"
        if not config_path.exists():
            return None

        in_project = False
        for raw_line in config_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue
            if raw_line.startswith("project:"):
                in_project = True
                continue
            if raw_line and not raw_line.startswith((" ", "\t")):
                in_project = False
            if in_project and raw_line.strip().startswith("entrypoint:"):
                value = raw_line.split(":", 1)[1].strip().strip("\"'")
                return value or None
        return None


class StreamlitCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.streamlit_apis: list[dict[str, object]] = []
        self.session_state: list[dict[str, object]] = []
        self.callbacks: list[dict[str, object]] = []
        self.caches: list[dict[str, object]] = []
        self.control_flow: list[dict[str, object]] = []

    def visit_Call(self, node: ast.Call) -> None:
        api_name = self._node_name(node.func)
        if api_name in STREAMLIT_APIS:
            record = self._api_record(api_name, node.lineno)
            self._record_api(record)
            if api_name in {"st.cache_data", "st.cache_resource"}:
                self.caches.append(record)
            if api_name in {"st.stop", "st.rerun"}:
                self.control_flow.append(record)

        for keyword in node.keywords:
            if keyword.arg in {"on_click", "on_change"}:
                self.callbacks.append(
                    {
                        "callback_type": keyword.arg,
                        "handler": self._node_name(keyword.value),
                        "line": node.lineno,
                    }
                )

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_decorators(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_decorators(node)
        self.generic_visit(node)

    def _record_decorators(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            api_name = self._decorator_name(decorator)
            if api_name in {"st.cache_data", "st.cache_resource"}:
                record = self._api_record(api_name, decorator.lineno)
                self._record_api(record)
                self.caches.append(record)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        api_name = self._node_name(node)
        if api_name == "st.session_state":
            self.session_state.append(
                {
                    "access": "attribute",
                    "key": None,
                    "line": node.lineno,
                }
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        api_name = self._node_name(node.value)
        if api_name == "st.session_state":
            self.session_state.append(
                {
                    "access": "subscript",
                    "key": self._literal_key(node.slice),
                    "line": node.lineno,
                }
            )
        self.generic_visit(node)

    def _api_record(self, api_name: str, line: int) -> dict[str, object]:
        return {
            "api": api_name,
            "category": self._category(api_name),
            "line": line,
        }

    def _record_api(self, record: dict[str, object]) -> None:
        self.streamlit_apis.append(record)

    def _decorator_name(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Call):
            return self._node_name(node.func)
        return self._node_name(node)

    def _category(self, api_name: str) -> str:
        if api_name in STREAMLIT_DISPLAY_APIS:
            return "display"
        if api_name in STREAMLIT_INPUT_APIS:
            return "input"
        if api_name in STREAMLIT_LAYOUT_APIS:
            return "layout"
        return "state_control"

    def _node_name(self, node: ast.AST | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._node_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return None

    @staticmethod
    def _literal_key(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant):
            return str(node.value)
        return None


def analyze_project_streamlit(
    project_path: Path,
    entry: str | None = None,
    output_path: Path | None = None,
) -> Path:
    return StreamlitAnalyzer().write_streamlit_index(project_path, entry, output_path)
