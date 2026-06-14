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


if __name__ == "__main__":
    unittest.main()
