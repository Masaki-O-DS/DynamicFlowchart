from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codeflow.cli import main


class CliTests(unittest.TestCase):
    def test_help_exits_successfully(self) -> None:
        with self.assertRaises(SystemExit) as context:
            main(["--help"])

        self.assertEqual(context.exception.code, 0)

    def test_init_creates_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(main(["init", temp_dir]), 0)
            config_path = Path(temp_dir) / "codeflow.yaml"

            self.assertTrue(config_path.exists())
            self.assertIn("schema_version: 1", config_path.read_text(encoding="utf-8"))

    def test_init_does_not_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "codeflow.yaml"
            config_path.write_text("existing: true\n", encoding="utf-8")

            self.assertEqual(main(["init", temp_dir]), 1)
            self.assertEqual(config_path.read_text(encoding="utf-8"), "existing: true\n")

    def test_scan_writes_project_index_with_python_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
            (root / "README.md").write_text("# sample\n", encoding="utf-8")
            (root / "test_app.py").write_text("def test_app():\n    pass\n", encoding="utf-8")
            (root / "service_test.py").write_text("def test_service():\n    pass\n", encoding="utf-8")
            (root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "worker.py").write_text("def run():\n    return 1\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_worker.py").write_text("def test_run():\n    pass\n", encoding="utf-8")
            (root / ".streamlit").mkdir()
            (root / ".streamlit" / "secrets.toml").write_text("token = 'x'\n", encoding="utf-8")
            (root / ".codex").mkdir()
            (root / ".codex" / "hook.py").write_text("print('local')\n", encoding="utf-8")

            self.assertEqual(main(["scan", temp_dir]), 0)

            index_path = root / ".codeflow" / "project_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            included_paths = {item["path"] for item in index["included_files"]}
            excluded = {item["path"]: item["reason"] for item in index["excluded_paths"]}

            self.assertEqual(included_paths, {"app.py", "src/worker.py"})
            self.assertEqual(index["summary"]["included_file_count"], 2)
            self.assertEqual(excluded["README.md"], "not_python_file")
            self.assertEqual(excluded["test_app.py"], "excluded_file_pattern")
            self.assertEqual(excluded["service_test.py"], "excluded_file_pattern")
            self.assertEqual(excluded[".env"], "excluded_file_pattern")
            self.assertEqual(excluded["tests"], "excluded_directory")
            self.assertEqual(excluded[".codex"], "excluded_directory")
            self.assertEqual(excluded[".streamlit/secrets.toml"], "excluded_file_pattern")

    def test_ast_writes_index_and_keeps_going_after_syntax_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "app.py").write_text(
                "import os\n"
                "from pathlib import Path\n\n"
                "def helper(value: int) -> str:\n"
                "    return str(value)\n\n"
                "class Runner:\n"
                "    def run(self):\n"
                "        return helper(1)\n",
                encoding="utf-8",
            )
            (root / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

            self.assertEqual(main(["ast", temp_dir]), 0)

            index_path = root / ".codeflow" / "ast_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            functions = {item["qualified_name"]: item for item in index["functions"]}

            self.assertEqual(index["summary"]["function_count"], 2)
            self.assertEqual(index["summary"]["error_count"], 1)
            self.assertIn("helper", functions)
            self.assertIn("Runner.run", functions)
            self.assertEqual(functions["helper"]["start_line"], 4)
            self.assertEqual(functions["helper"]["end_line"], 5)
            self.assertIn("return str(value)", functions["helper"]["code"])
            self.assertIn("str", functions["helper"]["called_functions"])
            self.assertIn("helper", functions["Runner.run"]["called_functions"])
            self.assertEqual(functions["helper"]["function_id"], "app.helper")
            self.assertEqual(functions["Runner.run"]["function_id"], "app.Runner.run")
            self.assertTrue(functions["helper"]["code_hash"])
            self.assertTrue(functions["helper"]["signature_hash"])
            self.assertTrue(functions["helper"]["call_hash"])
            self.assertTrue(functions["helper"]["dependency_hash"])
            self.assertEqual(index["imports"]["app.py"][0]["module"], "os")
            self.assertEqual(index["imports"]["app.py"][1]["module"], "pathlib")
            self.assertEqual(index["imports"]["app.py"][1]["name"], "Path")
            self.assertEqual(index["errors"][0]["file"], "broken.py")
            self.assertEqual(index["errors"][0]["error_type"], "SyntaxError")

    def test_streamlit_writes_index_and_extracts_streamlit_features(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "streamlit_app.py").write_text("print('lower priority')\n", encoding="utf-8")
            (root / "app.py").write_text("print('also lower priority')\n", encoding="utf-8")
            (root / "dashboard.py").write_text(
                "import streamlit as st\n\n"
                "@st.cache_data\n"
                "def load_data():\n"
                "    return [1]\n\n"
                "def clicked():\n"
                "    st.session_state['clicked'] = True\n\n"
                "st.set_page_config(page_title='Demo')\n"
                "st.title('Demo')\n"
                "value = st.text_input('Name', on_change=clicked)\n"
                "if st.button('Run', on_click=clicked):\n"
                "    st.session_state.result = load_data()\n"
                "st.stop()\n",
                encoding="utf-8",
            )
            (root / "pages").mkdir()
            (root / "pages" / "details.py").write_text(
                "import streamlit as st\nst.write('details')\n",
                encoding="utf-8",
            )

            self.assertEqual(main(["streamlit", temp_dir, "--entry", "dashboard.py"]), 0)

            index_path = root / ".codeflow" / "streamlit_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            dashboard = {
                item["file"]: item for item in index["files"]
            }["dashboard.py"]
            apis = {item["api"] for item in dashboard["streamlit_apis"]}
            callbacks = {item["callback_type"] for item in dashboard["callbacks"]}

            self.assertEqual(index["entrypoint"]["path"], "dashboard.py")
            self.assertEqual(index["entrypoint"]["source"], "cli")
            self.assertIn("pages/details.py", index["pages"])
            self.assertIn("st.set_page_config", apis)
            self.assertIn("st.title", apis)
            self.assertIn("st.text_input", apis)
            self.assertIn("st.button", apis)
            self.assertIn("st.stop", apis)
            self.assertIn("st.cache_data", apis)
            self.assertEqual(callbacks, {"on_click", "on_change"})
            self.assertTrue(dashboard["session_state"])
            self.assertEqual(dashboard["caches"][0]["api"], "st.cache_data")
            self.assertEqual(dashboard["control_flow"][0]["api"], "st.stop")

    def test_streamlit_entrypoint_inference_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pages").mkdir()
            (root / "pages" / "first.py").write_text("import streamlit as st\nst.write('x')\n", encoding="utf-8")
            (root / "other.py").write_text("import streamlit as st\nst.title('x')\nst.write('x')\n", encoding="utf-8")

            self.assertEqual(main(["streamlit", temp_dir]), 0)
            index = json.loads((root / ".codeflow" / "streamlit_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["entrypoint"]["path"], "pages/first.py")
            self.assertEqual(index["entrypoint"]["reason"], "pages/*.py")

            (root / "main.py").write_text("print('main')\n", encoding="utf-8")
            self.assertEqual(main(["streamlit", temp_dir]), 0)
            index = json.loads((root / ".codeflow" / "streamlit_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["entrypoint"]["path"], "main.py")
            self.assertEqual(index["entrypoint"]["reason"], "main.py")

            (root / "app.py").write_text("print('app')\n", encoding="utf-8")
            self.assertEqual(main(["streamlit", temp_dir]), 0)
            index = json.loads((root / ".codeflow" / "streamlit_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["entrypoint"]["path"], "app.py")
            self.assertEqual(index["entrypoint"]["reason"], "app.py")

            (root / "streamlit_app.py").write_text("print('streamlit')\n", encoding="utf-8")
            self.assertEqual(main(["streamlit", temp_dir]), 0)
            index = json.loads((root / ".codeflow" / "streamlit_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["entrypoint"]["path"], "streamlit_app.py")
            self.assertEqual(index["entrypoint"]["reason"], "streamlit_app.py")

            (root / "codeflow.yaml").write_text(
                "project:\n  entrypoint: other.py\n",
                encoding="utf-8",
            )
            self.assertEqual(main(["streamlit", temp_dir]), 0)
            index = json.loads((root / ".codeflow" / "streamlit_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["entrypoint"]["path"], "other.py")
            self.assertEqual(index["entrypoint"]["source"], "config")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "configured.py").write_text(
                "import streamlit as st\nst.set_page_config(page_title='Configured')\n",
                encoding="utf-8",
            )
            (root / "busy.py").write_text(
                "import streamlit as st\nst.title('Busy')\nst.write('x')\nst.button('Run')\n",
                encoding="utf-8",
            )

            self.assertEqual(main(["streamlit", temp_dir]), 0)
            index = json.loads((root / ".codeflow" / "streamlit_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["entrypoint"]["path"], "configured.py")
            self.assertEqual(index["entrypoint"]["reason"], "st.set_page_config")

            (root / "configured.py").write_text("print('plain')\n", encoding="utf-8")
            self.assertEqual(main(["streamlit", temp_dir]), 0)
            index = json.loads((root / ".codeflow" / "streamlit_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["entrypoint"]["path"], "busy.py")
            self.assertEqual(index["entrypoint"]["reason"], "streamlit_api_count")

    def test_analyze_writes_phase_five_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "app.py").write_text(
                "import streamlit as st\n\n"
                "def load():\n"
                "    return 1\n\n"
                "st.title('Demo')\n"
                "st.write(load())\n",
                encoding="utf-8",
            )

            self.assertEqual(main(["analyze", temp_dir, "--entry", "app.py"]), 0)

            output_dir = root / ".codeflow"
            expected_files = {
                "manifest.json",
                "project_index.json",
                "ast_index.json",
                "streamlit_index.json",
                "analysis_status.json",
                "analysis_report.md",
                "ai_plan.json",
            }
            self.assertEqual({path.name for path in output_dir.iterdir()}, expected_files)

            for file_name in expected_files - {"analysis_report.md"}:
                payload = json.loads((output_dir / file_name).read_text(encoding="utf-8"))
                self.assertEqual(payload["schema_version"], "0.7.0")

            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            status = json.loads((output_dir / "analysis_status.json").read_text(encoding="utf-8"))
            ai_plan = json.loads((output_dir / "ai_plan.json").read_text(encoding="utf-8"))
            report = (output_dir / "analysis_report.md").read_text(encoding="utf-8")

            self.assertIn("project_index.json", manifest["artifacts"])
            self.assertEqual(status["status"], "completed")
            self.assertEqual(ai_plan["status"], "pending")
            self.assertEqual(ai_plan["default_model"], "GLM-5")
            self.assertIn("CodeFlow Analysis Report", report)


if __name__ == "__main__":
    unittest.main()
