# CodeFlow Viewer

CodeFlow Viewer is a Python-first CLI tool for creating code understanding assets from Python and Streamlit projects.

This repository currently contains the Phase 1 CLI foundation.

## Usage

```bash
python3 -m pip install -e .
codeflow --help
codeflow init
```

Development checks can also run directly from the source tree:

```bash
PYTHONPATH=src python3 -m codeflow --help
PYTHONPATH=src python3 -m codeflow init
```
