"""Streamlit app for viewing saved CodeFlow artifacts."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


def load_json(data_dir: Path, name: str) -> dict[str, Any]:
    path = data_dir / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    import streamlit as st

    project_path = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
    data_dir = project_path / ".codeflow"

    manifest = load_json(data_dir, "manifest.json")
    status = load_json(data_dir, "analysis_status.json")
    flow_blocks = load_json(data_dir, "flow_blocks.json")
    function_summaries = load_json(data_dir, "function_summaries.json")
    line_explanations = load_json(data_dir, "line_explanations.json")

    st.set_page_config(page_title="CodeFlow Viewer", layout="wide")
    st.title("CodeFlow Viewer")
    st.caption(str(project_path))

    if not data_dir.exists():
        st.error(f"Missing .codeflow directory: {data_dir}")
        st.stop()

    summary = dict(status.get("summary", {}))
    columns = st.columns(4)
    columns[0].metric("Files", summary.get("included_file_count", 0))
    columns[1].metric("Functions", summary.get("function_count", 0))
    columns[2].metric("Flow blocks", summary.get("flow_block_count", 0))
    columns[3].metric("Errors", summary.get("error_count", 0))

    st.subheader("Artifacts")
    st.json(
        {
            "manifest": manifest.get("artifacts", []),
            "status": status.get("artifacts", {}),
            "ai_execution": "not_executed",
        },
        expanded=False,
    )

    st.subheader("Natural Language Flow")
    for block in flow_blocks.get("blocks", []):
        with st.expander(f"{block.get('block_id')} {block.get('title')}"):
            st.write(block.get("summary") or "Pending AI explanation.")
            st.json(
                {
                    "related_functions": block.get("related_functions", []),
                    "called_functions": block.get("called_functions", []),
                    "status": block.get("status"),
                    "review_status": block.get("review_status"),
                },
                expanded=False,
            )

    st.subheader("Function Summaries")
    functions = function_summaries.get("functions", [])
    for function in functions:
        st.markdown(f"**{function.get('qualified_name')}**")
        st.caption(f"{function.get('file')}:{function.get('start_line')}-{function.get('end_line')}")
        st.write(function.get("summary") or "Pending AI summary.")

    st.subheader("Line Explanations")
    explanation_functions = line_explanations.get("functions", [])
    if not explanation_functions:
        st.info("No line explanations are available.")
        return

    selected = st.selectbox("Function", [item.get("function_id") for item in explanation_functions])
    for function in line_explanations.get("functions", []):
        if function.get("function_id") == selected:
            for line in function.get("line_items", []):
                st.code(f"{line.get('line')}: {line.get('code')}", language="python")
                st.caption(line.get("explanation") or "Pending AI line explanation.")


if __name__ == "__main__":
    main()
