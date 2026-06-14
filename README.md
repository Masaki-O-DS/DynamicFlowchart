# CodeFlow Viewer

CodeFlow Viewer is a Python-first CLI tool for creating code understanding assets from Python and Streamlit projects.

This repository currently contains the Phase 1 CLI foundation, Phase 2 project scanner, Phase 3 AST analyzer, Phase 4 Streamlit analyzer, and Phase 5 storage/analyze command.

## Usage

```bash
python3 -m pip install -e .
codeflow --help
codeflow init
codeflow scan .
codeflow ast .
codeflow streamlit .
codeflow analyze .
```

If an older pip tries to download build tools during editable install, use the legacy local path:

```bash
python3 -m pip install -e . --no-use-pep517
```

Development checks can also run directly from the source tree:

```bash
PYTHONPATH=src python3 -m codeflow --help
PYTHONPATH=src python3 -m codeflow init
PYTHONPATH=src python3 -m codeflow scan .
PYTHONPATH=src python3 -m codeflow ast .
PYTHONPATH=src python3 -m codeflow streamlit .
PYTHONPATH=src python3 -m codeflow analyze .
```
