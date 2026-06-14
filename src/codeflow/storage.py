"""Storage orchestration for CodeFlow analysis artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from codeflow.ai_plan import AiPlanBuilder
from codeflow import __version__
from codeflow.ast_analyzer import AstAnalyzer
from codeflow.config import SCHEMA_VERSION
from codeflow.flow_artifacts import FlowArtifactBuilder
from codeflow.scanner import ProjectScanner
from codeflow.streamlit_analyzer import StreamlitAnalyzer


class StorageBuilder:
    """Run the current analyzers and persist CodeFlow artifacts."""

    def analyze(self, project_path: Path, entry: str | None = None) -> dict[str, object]:
        root = project_path.expanduser().resolve()
        output_dir = root / ".codeflow"
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(timezone.utc).isoformat()

        project_index = ProjectScanner().scan(root)
        ast_index = AstAnalyzer().analyze(root)
        streamlit_index = StreamlitAnalyzer().analyze(root, entry=entry)

        manifest = self._manifest(root, generated_at, entry)
        ai_plan = AiPlanBuilder().build(root, ast_index=ast_index, generated_at=generated_at)
        flow_artifacts = FlowArtifactBuilder().build(ast_index, streamlit_index, generated_at=generated_at)
        analysis_status = self._analysis_status(
            project_index,
            ast_index,
            streamlit_index,
            flow_artifacts,
            generated_at,
        )
        report = self._analysis_report(project_index, ast_index, streamlit_index)

        written_files = {
            "manifest": self._write_json(output_dir / "manifest.json", manifest),
            "project_index": self._write_json(output_dir / "project_index.json", project_index),
            "ast_index": self._write_json(output_dir / "ast_index.json", ast_index),
            "streamlit_index": self._write_json(output_dir / "streamlit_index.json", streamlit_index),
            "flow_blocks": self._write_json(output_dir / "flow_blocks.json", flow_artifacts["flow_blocks"]),
            "function_summaries": self._write_json(
                output_dir / "function_summaries.json",
                flow_artifacts["function_summaries"],
            ),
            "line_explanations": self._write_json(
                output_dir / "line_explanations.json",
                flow_artifacts["line_explanations"],
            ),
            "explanation_versions": self._write_json(
                output_dir / "explanation_versions.json",
                flow_artifacts["explanation_versions"],
            ),
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
                "flow_blocks.json",
                "function_summaries.json",
                "line_explanations.json",
                "explanation_versions.json",
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
        flow_artifacts: dict[str, dict[str, object]],
        generated_at: str,
    ) -> dict[str, object]:
        ast_errors = int(dict(ast_index["summary"])["error_count"])
        streamlit_errors = int(dict(streamlit_index["summary"])["error_count"])
        status = "completed_with_errors" if ast_errors or streamlit_errors else "completed"
        flow_blocks = dict(flow_artifacts["flow_blocks"])
        function_summaries = dict(flow_artifacts["function_summaries"])
        line_explanations = dict(flow_artifacts["line_explanations"])
        return {
            "schema_version": SCHEMA_VERSION,
            "codeflow_version": __version__,
            "created_at": generated_at,
            "status": status,
            "artifacts": {
                "project_index": "generated",
                "ast_index": "generated",
                "streamlit_index": "generated",
                "flow_blocks": flow_blocks["status"],
                "function_summaries": function_summaries["status"],
                "line_explanations": line_explanations["status"],
                "explanation_versions": "empty",
                "analysis_report": "generated",
                "ai_plan": "generated",
            },
            "summary": {
                "included_file_count": dict(project_index["summary"])["included_file_count"],
                "function_count": dict(ast_index["summary"])["function_count"],
                "streamlit_file_count": dict(streamlit_index["summary"])["streamlit_file_count"],
                "flow_block_count": dict(flow_blocks["summary"])["block_count"],
                "pending_function_summary_count": dict(function_summaries["summary"])["pending_count"],
                "pending_line_explanation_count": dict(line_explanations["summary"])["pending_count"],
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
                f"- Flow blocks: {ast_summary['function_count']}",
                f"- AST errors: {ast_summary['error_count']}",
                f"- Streamlit files: {streamlit_summary['streamlit_file_count']}",
                f"- Streamlit pages: {streamlit_summary['page_count']}",
                f"- Streamlit entrypoint: {entrypoint['path'] or 'not found'}",
                f"- Entrypoint reason: {entrypoint['reason']}",
                f"- Explanation status: pending AI for {ast_summary['function_count']} functions",
                "",
                "## Artifacts",
                "",
                "- manifest.json",
                "- project_index.json",
                "- ast_index.json",
                "- streamlit_index.json",
                "- flow_blocks.json",
                "- function_summaries.json",
                "- line_explanations.json",
                "- explanation_versions.json",
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
