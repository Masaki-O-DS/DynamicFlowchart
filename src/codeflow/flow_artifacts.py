"""Flow blocks and explanation placeholders for CodeFlow Viewer."""

from __future__ import annotations

from datetime import datetime, timezone

from codeflow import __version__
from codeflow.config import SCHEMA_VERSION


class FlowArtifactBuilder:
    """Build AI-ready flow and explanation artifacts without calling AI."""

    def build(
        self,
        ast_index: dict[str, object],
        streamlit_index: dict[str, object],
        generated_at: str | None = None,
    ) -> dict[str, dict[str, object]]:
        created_at = generated_at or datetime.now(timezone.utc).isoformat()
        functions = list(ast_index["functions"])
        streamlit_entrypoint = dict(streamlit_index["entrypoint"])

        return {
            "flow_blocks": self._flow_blocks(functions, streamlit_entrypoint, created_at),
            "function_summaries": self._function_summaries(functions, created_at),
            "line_explanations": self._line_explanations(functions, created_at),
            "explanation_versions": self._explanation_versions(created_at),
        }

    def _base_payload(self, created_at: str) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "codeflow_version": __version__,
            "created_at": created_at,
        }

    def _flow_blocks(
        self,
        functions: list[object],
        streamlit_entrypoint: dict[str, object],
        created_at: str,
    ) -> dict[str, object]:
        blocks: list[dict[str, object]] = []
        for index, raw_function in enumerate(functions, start=1):
            function = dict(raw_function)
            function_id = str(function["function_id"])
            qualified_name = str(function["qualified_name"])

            blocks.append(
                {
                    "block_id": f"block_{index:03d}",
                    "title": qualified_name,
                    "summary": None,
                    "related_functions": [function_id],
                    "file": function["file"],
                    "start_line": function["start_line"],
                    "end_line": function["end_line"],
                    "called_functions": list(function["called_functions"]),
                    "status": "pending_ai",
                    "model": "GLM-5",
                    "confidence": "unknown",
                    "review_status": "unreviewed",
                    "source": "ast_placeholder",
                }
            )

        payload = self._base_payload(created_at)
        payload.update(
            {
                "status": "pending_ai" if blocks else "empty",
                "entrypoint": streamlit_entrypoint,
                "summary": {
                    "block_count": len(blocks),
                    "function_count": len(functions),
                },
                "blocks": blocks,
                "notes": [
                    "Flow block summaries are placeholders until AI execution is implemented.",
                    "UI viewing and export commands can read this file without calling AI.",
                ],
            }
        )
        return payload

    def _function_summaries(self, functions: list[object], created_at: str) -> dict[str, object]:
        summaries: list[dict[str, object]] = []
        for raw_function in functions:
            function = dict(raw_function)
            summaries.append(
                {
                    "function_id": function["function_id"],
                    "name": function["name"],
                    "qualified_name": function["qualified_name"],
                    "file": function["file"],
                    "start_line": function["start_line"],
                    "end_line": function["end_line"],
                    "code_hash": function["code_hash"],
                    "dependency_hash": function["dependency_hash"],
                    "summary": None,
                    "status": "pending_ai",
                    "model": "GLM-5",
                    "confidence": "unknown",
                    "review_status": "unreviewed",
                    "prompt_version": None,
                    "generated_at": None,
                }
            )

        payload = self._base_payload(created_at)
        payload.update(
            {
                "status": "pending_ai" if summaries else "empty",
                "summary": {
                    "function_count": len(functions),
                    "pending_count": len(summaries),
                    "generated_count": 0,
                },
                "functions": summaries,
            }
        )
        return payload

    def _line_explanations(self, functions: list[object], created_at: str) -> dict[str, object]:
        explanations: list[dict[str, object]] = []
        line_count = 0
        for raw_function in functions:
            function = dict(raw_function)
            start_line = int(function["start_line"])
            line_items = []
            for offset, code_line in enumerate(str(function["code"]).splitlines()):
                line_items.append(
                    {
                        "line": start_line + offset,
                        "code": code_line,
                        "explanation": None,
                        "status": "pending_ai",
                    }
                )
            line_count += len(line_items)
            explanations.append(
                {
                    "function_id": function["function_id"],
                    "file": function["file"],
                    "start_line": function["start_line"],
                    "end_line": function["end_line"],
                    "code_hash": function["code_hash"],
                    "line_items": line_items,
                    "status": "pending_ai" if line_items else "empty",
                    "model": "GLM-5",
                    "confidence": "unknown",
                    "review_status": "unreviewed",
                    "prompt_version": None,
                    "generated_at": None,
                }
            )

        payload = self._base_payload(created_at)
        payload.update(
            {
                "status": "pending_ai" if explanations else "empty",
                "summary": {
                    "function_count": len(functions),
                    "line_count": line_count,
                    "pending_count": line_count,
                    "generated_count": 0,
                },
                "functions": explanations,
            }
        )
        return payload

    def _explanation_versions(self, created_at: str) -> dict[str, object]:
        payload = self._base_payload(created_at)
        payload.update(
            {
                "status": "empty",
                "summary": {
                    "version_count": 0,
                    "manual_edit_count": 0,
                    "improvement_count": 0,
                },
                "versions": [],
                "notes": [
                    "Version history is empty until AI generation, manual edits, or improvements are implemented.",
                ],
            }
        )
        return payload
