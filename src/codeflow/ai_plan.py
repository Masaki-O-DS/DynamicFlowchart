"""AI planning boundary for CodeFlow Viewer."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from codeflow import __version__
from codeflow.ast_analyzer import AstAnalyzer
from codeflow.config import SCHEMA_VERSION


class AiPlanBuilder:
    """Estimate AI work without executing any AI calls."""

    def build(
        self,
        project_path: Path,
        ast_index: dict[str, object] | None = None,
        generated_at: str | None = None,
    ) -> dict[str, object]:
        root = project_path.expanduser().resolve()
        current_ast = ast_index or AstAnalyzer().analyze(root)
        previous_ast = self._read_previous_ast(root)
        reusable_functions = self._reusable_function_count(current_ast, previous_ast)
        function_count = int(dict(current_ast["summary"])["function_count"])
        functions_requiring_ai = max(function_count - reusable_functions, 0)
        natural_language_flow_calls = 1 if functions_requiring_ai else 0
        total_calls = functions_requiring_ai * 2 + natural_language_flow_calls

        return {
            "schema_version": SCHEMA_VERSION,
            "codeflow_version": __version__,
            "created_at": generated_at or datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "ai_adapter": {
                "provider": "kiro_cli",
                "configured": False,
                "status": "pending",
            },
            "model": {
                "default": "GLM-5",
                "auto_fallback": False,
                "manual_improvement_models": [],
            },
            "targets": {
                "file_count": int(dict(current_ast["summary"])["file_count"]),
                "function_count": function_count,
            },
            "planned_calls": {
                "function_summaries": functions_requiring_ai,
                "line_explanations": functions_requiring_ai,
                "natural_language_flow": natural_language_flow_calls,
                "total": total_calls,
            },
            "cache_reuse": {
                "function_summaries": reusable_functions,
                "line_explanations": reusable_functions,
                "natural_language_flow": 1 if function_count and not functions_requiring_ai else 0,
                "function_count": reusable_functions,
            },
            "notes": [
                "AI execution is not implemented in this phase.",
                "This command only writes ai_plan.json and prints the plan.",
                "UI viewing and export commands must not call AI.",
            ],
        }

    def write_plan(self, project_path: Path, output_path: Path | None = None) -> tuple[Path, dict[str, object]]:
        root = project_path.expanduser().resolve()
        plan = self.build(root)
        destination = output_path or (root / ".codeflow" / "ai_plan.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination, plan

    def format_summary(self, plan: dict[str, object], output_path: Path) -> str:
        targets = dict(plan["targets"])
        planned_calls = dict(plan["planned_calls"])
        cache_reuse = dict(plan["cache_reuse"])
        model = dict(plan["model"])
        adapter = dict(plan["ai_adapter"])
        lines = [
            f"Target files: {targets['file_count']}",
            f"Target functions: {targets['function_count']}",
            "AI calls required:",
            f"- Function summaries: {planned_calls['function_summaries']}",
            f"- Line explanations: {planned_calls['line_explanations']}",
            f"- Natural language flow: {planned_calls['natural_language_flow']}",
            f"- Total: {planned_calls['total']}",
            "Cache reuse:",
            f"- Function summaries: {cache_reuse['function_summaries']}",
            f"- Line explanations: {cache_reuse['line_explanations']}",
            f"- Natural language flow: {cache_reuse['natural_language_flow']}",
            "Planned model:",
            f"- default: {model['default']}",
            f"- auto_fallback: {str(model['auto_fallback']).lower()}",
            "AI adapter:",
            f"- provider: {adapter['provider']}",
            f"- configured: {str(adapter['configured']).lower()}",
            f"- status: {adapter['status']}",
            "High-capability models:",
            "- none",
            "AI execution:",
            "- not executed",
            f"Saved: {output_path}",
        ]
        return "\n".join(lines)

    def _read_previous_ast(self, root: Path) -> dict[str, object] | None:
        path = root / ".codeflow" / "ast_index.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _reusable_function_count(
        self,
        current_ast: dict[str, object],
        previous_ast: dict[str, object] | None,
    ) -> int:
        if previous_ast is None:
            return 0
        previous_hashes = {
            str(function["function_id"]): str(function["code_hash"])
            for function in previous_ast.get("functions", [])
        }
        return sum(
            1
            for function in current_ast.get("functions", [])
            if previous_hashes.get(str(function["function_id"])) == str(function["code_hash"])
        )
