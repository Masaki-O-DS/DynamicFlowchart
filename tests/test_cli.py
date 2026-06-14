from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
