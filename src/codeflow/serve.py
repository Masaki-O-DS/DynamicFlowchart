"""Launch the saved CodeFlow Viewer UI without calling AI."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


REQUIRED_ARTIFACTS = (
    "manifest.json",
    "project_index.json",
    "ast_index.json",
    "streamlit_index.json",
    "flow_blocks.json",
    "function_summaries.json",
    "line_explanations.json",
    "analysis_status.json",
    "ai_plan.json",
)


@dataclass(frozen=True)
class ServePlan:
    project_path: Path
    data_dir: Path
    url: str
    command: list[str]
    missing_artifacts: list[str]


class ServeLauncher:
    """Validate saved artifacts and launch Streamlit when available."""

    def build_plan(self, project_path: Path, host: str = "localhost", port: int = 8501) -> ServePlan:
        root = project_path.expanduser().resolve()
        data_dir = root / ".codeflow"
        missing = [name for name in REQUIRED_ARTIFACTS if not (data_dir / name).exists()]
        app_path = Path(__file__).with_name("viewer_app.py")
        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--server.address",
            host,
            "--server.port",
            str(port),
            "--",
            str(root),
        ]
        return ServePlan(
            project_path=root,
            data_dir=data_dir,
            url=f"http://{host}:{port}",
            command=command,
            missing_artifacts=missing,
        )

    def validate(self, plan: ServePlan) -> list[str]:
        errors: list[str] = []
        if not plan.data_dir.exists():
            errors.append(f"Missing data directory: {plan.data_dir}")
            return errors

        errors.extend(f"Missing artifact: {name}" for name in plan.missing_artifacts)
        for artifact_name in REQUIRED_ARTIFACTS:
            artifact_path = plan.data_dir / artifact_name
            if artifact_path.exists():
                try:
                    json.loads(artifact_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    errors.append(f"Invalid JSON in {artifact_name}: {error.msg}")
        return errors

    def run(self, plan: ServePlan, dry_run: bool = False) -> int:
        errors = self.validate(plan)
        if errors:
            for error in errors:
                print(error)
            print("Run codeflow analyze before codeflow serve.")
            return 1

        self.print_startup(plan)
        print("AI execution: not executed")
        if dry_run:
            print(f"Command: {self.format_command(plan.command)}")
            return 0

        if importlib.util.find_spec("streamlit") is None:
            print("Streamlit is not installed in this Python environment.")
            print("Install Streamlit, then run this command again.")
            print(f"Command: {self.format_command(plan.command)}")
            return 1

        return int(subprocess.run(plan.command, check=False).returncode)

    @staticmethod
    def print_startup(plan: ServePlan) -> None:
        print("Starting CodeFlow Viewer...")
        print(f"Project: {plan.project_path}")
        print(f"Data: {plan.data_dir}")
        print(f"URL: {plan.url}")

    @staticmethod
    def format_command(command: list[str]) -> str:
        return " ".join(command)
