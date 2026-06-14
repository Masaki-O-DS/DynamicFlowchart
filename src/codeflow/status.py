"""Status reporting for saved CodeFlow artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codeflow.ast_analyzer import AstAnalyzer
from codeflow.serve import REQUIRED_ARTIFACTS


class StatusReporter:
    """Compare current source analysis with saved .codeflow artifacts."""

    def build(self, project_path: Path) -> dict[str, object]:
        root = project_path.expanduser().resolve()
        data_dir = root / ".codeflow"
        artifacts = self._read_artifacts(data_dir)
        missing = [name for name in REQUIRED_ARTIFACTS if name not in artifacts]

        current_ast = AstAnalyzer().analyze(root)
        saved_ast = artifacts.get("ast_index.json", {})
        function_summaries = artifacts.get("function_summaries.json", {})
        line_explanations = artifacts.get("line_explanations.json", {})
        flow_blocks = artifacts.get("flow_blocks.json", {})
        analysis_status = artifacts.get("analysis_status.json", {})
        ai_plan = artifacts.get("ai_plan.json", {})

        source_diff = self._source_diff(current_ast, saved_ast)
        function_summary_counts = self._item_status_counts(function_summaries.get("functions", []))
        line_explanation_counts = self._line_status_counts(line_explanations.get("functions", []))

        return {
            "project_path": root,
            "data_dir": data_dir,
            "missing_artifacts": missing,
            "current": {
                "file_count": int(dict(current_ast["summary"])["file_count"]),
                "function_count": int(dict(current_ast["summary"])["function_count"]),
                "error_count": int(dict(current_ast["summary"])["error_count"]),
            },
            "saved": {
                "status": analysis_status.get("status", "missing"),
                "flow_status": flow_blocks.get("status", "missing"),
                "function_summaries": function_summary_counts,
                "line_explanations": line_explanation_counts,
                "ai_failures": int(dict(analysis_status.get("summary", {})).get("error_count", 0)),
                "cache_reuse": dict(ai_plan.get("cache_reuse", {})).get("function_count", 0),
            },
            "source_diff": source_diff,
            "review": {
                "unreviewed": self._review_count(function_summaries.get("functions", []), "unreviewed"),
                "human_edited": self._human_edited_count(function_summaries.get("functions", [])),
            },
        }

    def format_summary(self, status: dict[str, object]) -> str:
        current = dict(status["current"])
        saved = dict(status["saved"])
        source_diff = dict(status["source_diff"])
        review = dict(status["review"])
        function_summaries = dict(saved["function_summaries"])
        line_explanations = dict(saved["line_explanations"])
        missing_artifacts = list(status["missing_artifacts"])

        lines = [
            f"Project: {status['project_path']}",
            f"Data: {status['data_dir']}",
            f"Artifacts: {'missing' if missing_artifacts else 'ready'}",
        ]
        if missing_artifacts:
            lines.append(f"Missing artifacts: {', '.join(missing_artifacts)}")

        lines.extend(
            [
                f"Analysis status: {saved['status']}",
                f"Target files: {current['file_count']}",
                f"Target functions: {current['function_count']}",
                "Source diff:",
                f"- unchanged: {source_diff['unchanged']}",
                f"- changed: {source_diff['changed']}",
                f"- new: {source_diff['new']}",
                f"- removed: {source_diff['removed']}",
                f"- current AST errors: {current['error_count']}",
                f"Natural language flow: {saved['flow_status']}",
                (
                    "Function summaries: "
                    f"{function_summaries['generated']} generated / "
                    f"{function_summaries['total']} total "
                    f"({function_summaries['pending']} pending)"
                ),
                (
                    "Line explanations: "
                    f"{line_explanations['generated']} generated / "
                    f"{line_explanations['total']} total "
                    f"({line_explanations['pending']} pending)"
                ),
                f"AI generation failures: {saved['ai_failures']}",
                f"Cache reuse: {saved['cache_reuse']}",
                f"Unreviewed explanations: {review['unreviewed']}",
                f"Human edited explanations: {review['human_edited']}",
                "AI execution: not executed",
            ]
        )
        return "\n".join(lines)

    def _read_artifacts(self, data_dir: Path) -> dict[str, dict[str, Any]]:
        artifacts: dict[str, dict[str, Any]] = {}
        if not data_dir.exists():
            return artifacts

        for artifact_name in REQUIRED_ARTIFACTS:
            artifact_path = data_dir / artifact_name
            if not artifact_path.exists():
                continue
            try:
                artifacts[artifact_name] = json.loads(artifact_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                artifacts[artifact_name] = {}
        return artifacts

    def _source_diff(
        self,
        current_ast: dict[str, object],
        saved_ast: dict[str, Any],
    ) -> dict[str, int]:
        current_hashes = self._function_hashes(current_ast)
        saved_hashes = self._function_hashes(saved_ast)
        current_ids = set(current_hashes)
        saved_ids = set(saved_hashes)
        common_ids = current_ids & saved_ids

        return {
            "unchanged": sum(
                1
                for function_id in common_ids
                if current_hashes[function_id] == saved_hashes[function_id]
            ),
            "changed": sum(
                1
                for function_id in common_ids
                if current_hashes[function_id] != saved_hashes[function_id]
            ),
            "new": len(current_ids - saved_ids),
            "removed": len(saved_ids - current_ids),
        }

    @staticmethod
    def _function_hashes(ast_index: dict[str, Any]) -> dict[str, str]:
        return {
            str(function["function_id"]): str(function["code_hash"])
            for function in ast_index.get("functions", [])
            if "function_id" in function and "code_hash" in function
        }

    @staticmethod
    def _item_status_counts(items: list[object]) -> dict[str, int]:
        total = len(items)
        generated = sum(1 for item in items if dict(item).get("status") == "generated")
        pending = sum(1 for item in items if dict(item).get("status") == "pending_ai")
        return {
            "total": total,
            "generated": generated,
            "pending": pending,
        }

    @staticmethod
    def _line_status_counts(functions: list[object]) -> dict[str, int]:
        total = 0
        generated = 0
        pending = 0
        for raw_function in functions:
            function = dict(raw_function)
            for raw_line in function.get("line_items", []):
                line = dict(raw_line)
                total += 1
                if line.get("status") == "generated":
                    generated += 1
                if line.get("status") == "pending_ai":
                    pending += 1
        return {
            "total": total,
            "generated": generated,
            "pending": pending,
        }

    @staticmethod
    def _review_count(items: list[object], review_status: str) -> int:
        return sum(1 for item in items if dict(item).get("review_status") == review_status)

    @staticmethod
    def _human_edited_count(items: list[object]) -> int:
        return sum(
            1
            for item in items
            if dict(item).get("review_status") in {"edited", "human_edited"}
        )
