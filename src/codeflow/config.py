"""Shared defaults for CodeFlow Viewer."""

SCHEMA_VERSION = "0.7.0"

DEFAULT_EXCLUDE_DIRS = (
    "test",
    "tests",
    "__pycache__",
    "venv",
    ".venv",
    ".git",
    "node_modules",
    ".codeflow",
    ".codex",
    ".agents",
)

DEFAULT_EXCLUDE_FILES = (
    "test_*.py",
    "*_test.py",
    ".env",
    "*.pem",
    "*.key",
    "*.crt",
    ".streamlit/secrets.toml",
)

DEFAULT_CONFIG = """# CodeFlow Viewer configuration
schema_version: 1
project:
  name: ""
scanner:
  include:
    - "**/*.py"
  exclude_dirs:
    - test
    - tests
    - __pycache__
    - venv
    - .venv
    - .git
    - node_modules
    - .codeflow
    - .codex
    - .agents
  exclude_files:
    - "test_*.py"
    - "*_test.py"
    - ".env"
    - "*.pem"
    - "*.key"
    - "*.crt"
    - ".streamlit/secrets.toml"
ai:
  default_model: "GLM-5"
  auto_fallback: false
"""
