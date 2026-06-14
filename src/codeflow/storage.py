"""Storage orchestration for CodeFlow analysis artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from codeflow.ai_plan import AiPlanBuilder
from codeflow import __version__
from codeflow.ast_analyzer import AstAnalyzer
from codeflow.config import SCHEMA_VERSION
from codeflow.scanner import ProjectScanner
from codeflow.streamlit_analyzer import StreamlitAnalyzer


class StorageBuilder:
    """Run the current analyzers and persist Phase 5 artifacts."""

    def analyze(self, project_path: Path, entry: str | None = None) -> dict[str, object]:
        root = project_path.expanduser().resolve()
        output_dir = root / ".codeflow"
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(timezone.utc).isoformat()

        project_index = ProjectScanner().scan(root)
        ast_index = AstAnalyzer().analyze(root)
        streamlit_index = StreamlitAnalyzer().analyze(root, entry=entry)

        manifest = self._manifest(root, generated_at, entry)
        analysis_status = self._analysis_status(project_index, ast_index, streamlit_index, generated_at)
        ai_plan = AiPlanBuilder().build(root, ast_index=ast_index, generated_at=generated_at)
        report = self._analysis_report(project_index, ast_index, streamlit_index)

        written_files = {
            "manifest": self._write_json(output_dir / "manifest.json", manifest),
            "project_index": self._write_json(output_dir / "project_index.json", project_index),
            "ast_index": self._write_json(output_dir / "ast_index.json", ast_index),
            "streamlit_index": self._write_json(output_dir / "streamlit_index.json", streamlit_index),
            "analysis_status": self._write_json(output_dir / "analysis_status.json", analysis_status),
            "ai_plan": self._write_json(output_dir / "ai_plan.json", ai_plan),
            "analysis_report": self._write_text(output_dir / "analysis_report.md", report),
        }

        return {
            "output_dir": output_dir,
            "written_files": written_files,
            "manifest": manifest,
        }

    def _manifest(self, root: Path, generated_at: str, entry: str | None) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "codeflow_version": __version__,
            "created_at": generated_at,
            "project_root": str(root),
            "entry": entry,
            "artifacts": [
                "manifest.json",
                "project_index.json",
                "ast_index.json",
                "streamlit_index.json",
                "analysis_status.json",
                "analysis_report.md",
                "ai_plan.json",
            ],
        }

    def _analysis_status(
        self,
        project_index: dict[str, object],
        ast_index: dict[str, object],
        streamlit_index: dict[str, object],
        generated_at: str,
    ) -> dict[str, object]:
        ast_errors = int(dict(ast_index["summary"])["error_count"])
        streamlit_errors = int(dict(streamlit_index["summary"])["error_count"])
        status = "completed_with_errors" if ast_errors or streamlit_errors else "completed"
        return {
            "schema_version": SCHEMA_VERSION,
            "codeflow_version": __version__,
            "created_at": generated_at,
            "status": status,
            "artifacts": {
                "project_index": "generated",
                "ast_index": "generated",
                "streamlit_index": "generated",
                "analysis_report": "generated",
                "ai_plan": "generated",
            },
            "summary": {
                "included_file_count": dict(project_index["summary"])["included_file_count"],
                "function_count": dict(ast_index["summary"])["function_count"],
                "streamlit_file_count": dict(streamlit_index["summary"])["streamlit_file_count"],
                "error_count": ast_errors + streamlit_errors,
            },
        }

    def _analysis_report(
        self,
        project_index: dict[str, object],
        ast_index: dict[str, object],
        streamlit_index: dict[str, object],
    ) -> str:
        project_summary = dict(project_index["summary"])
        ast_summary = dict(ast_index["summary"])
        streamlit_summary = dict(streamlit_index["summary"])
        entrypoint = dict(streamlit_index["entrypoint"])
        return "\n".join(
            [
                "# CodeFlow Analysis Report",
                "",
                "## Summary",
                "",
                f"- Included Python files: {project_summary['included_file_count']}",
                f"- Excluded paths: {project_summary['excluded_path_count']}",
                f"- Functions: {ast_summary['function_count']}",
                f"- AST errors: {ast_summary['error_count']}",
                f"- Streamlit files: {streamlit_summary['streamlit_file_count']}",
                f"- Streamlit pages: {streamlit_summary['page_count']}",
                f"- Streamlit entrypoint: {entrypoint['path'] or 'not found'}",
                f"- Entrypoint reason: {entrypoint['reason']}",
                "",
                "## Artifacts",
                "",
                "- manifest.json",
                "- project_index.json",
                "- ast_index.json",
                "- streamlit_index.json",
                "- analysis_status.json",
                "- ai_plan.json",
                "",
            ]
        )

    @staticmethod
    def _write_json(path: Path, content: dict[str, object]) -> Path:
        path.write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _write_text(path: Path, content: str) -> Path:
        path.write_text(content, encoding="utf-8")
        return path


def analyze_project(project_path: Path, entry: str | None = None) -> dict[str, object]:
    return StorageBuilder().analyze(project_path, entry=entry)
