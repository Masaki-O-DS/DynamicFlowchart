"""Static AST analyzer for Python source files."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable

from codeflow import __version__
from codeflow.config import SCHEMA_VERSION
from codeflow.scanner import ProjectScanner


@dataclass(frozen=True)
class SourceFile:
    path: Path
    relative_path: str


class AstAnalyzer:
    """Extract function structures and resiliently record parse errors."""

    def analyze(self, project_path: Path) -> dict[str, object]:
        root = project_path.expanduser().resolve()
        project_index = ProjectScanner().scan(root)
        source_files = [
            SourceFile(root / str(item["path"]), str(item["path"]))
            for item in project_index["included_files"]
        ]

        functions: list[dict[str, object]] = []
        imports_by_file: dict[str, list[dict[str, object]]] = {}
        errors: list[dict[str, object]] = []

        for source_file in source_files:
            try:
                file_functions, file_imports = self._analyze_file(source_file)
            except SyntaxError as error:
                errors.append(
                    {
                        "file": source_file.relative_path,
                        "error_type": "SyntaxError",
                        "message": error.msg,
                        "line": error.lineno,
                        "offset": error.offset,
                    }
                )
                continue
            except OSError as error:
                errors.append(
                    {
                        "file": source_file.relative_path,
                        "error_type": error.__class__.__name__,
                        "message": str(error),
                    }
                )
                continue

            functions.extend(file_functions)
            imports_by_file[source_file.relative_path] = file_imports

        function_hashes: dict[str, str] = {}
        for function in functions:
            code_hash = str(function["code_hash"])
            function_hashes[str(function["function_id"])] = code_hash
            function_hashes[str(function["qualified_name"])] = code_hash
            function_hashes[str(function["name"])] = code_hash
        for function in functions:
            called_hashes = [
                function_hashes[name]
                for name in function["called_functions"]
                if name in function_hashes
            ]
            function["dependency_hash"] = self._stable_hash(
                [
                    str(function["code_hash"]),
                    str(function["call_hash"]),
                    *sorted(called_hashes),
                ]
            )

        return {
            "schema_version": SCHEMA_VERSION,
            "codeflow_version": __version__,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_root": str(root),
            "summary": {
                "file_count": len(source_files),
                "analyzed_file_count": len(imports_by_file),
                "function_count": len(functions),
                "error_count": len(errors),
            },
            "functions": functions,
            "imports": imports_by_file,
            "errors": errors,
        }

    def write_ast_index(self, project_path: Path, output_path: Path | None = None) -> Path:
        root = project_path.expanduser().resolve()
        index = self.analyze(root)
        destination = output_path or (root / ".codeflow" / "ast_index.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination

    def _analyze_file(
        self,
        source_file: SourceFile,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        source = source_file.path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source, filename=source_file.relative_path)
        parent_names: list[str] = []
        imports = ImportCollector().collect(tree)
        functions: list[dict[str, object]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        parent_names.append(node.name)
                        functions.append(
                            self._function_record(source_file.relative_path, item, lines, parent_names)
                        )
                        parent_names.pop()
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self._is_method_node(tree, node):
                    continue
                functions.append(self._function_record(source_file.relative_path, node, lines, []))

        functions.sort(key=lambda item: (str(item["file"]), int(item["start_line"]), str(item["name"])))
        return functions, imports

    def _function_record(
        self,
        relative_path: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
        parent_names: list[str],
    ) -> dict[str, object]:
        end_line = getattr(node, "end_lineno", node.lineno)
        code = "\n".join(lines[node.lineno - 1 : end_line])
        qualified_name = ".".join([*parent_names, node.name])
        module_name = relative_path.removesuffix(".py").replace("/", ".")
        function_id = f"{module_name}.{qualified_name}"
        called_functions = sorted(CallCollector().collect(node))
        imports = ImportCollector().collect(node)
        signature = self._signature_source(node)

        return {
            "function_id": function_id,
            "name": node.name,
            "qualified_name": qualified_name,
            "file": relative_path,
            "start_line": node.lineno,
            "end_line": end_line,
            "code": code,
            "called_functions": called_functions,
            "imports": imports,
            "code_hash": self._stable_hash([code]),
            "signature_hash": self._stable_hash([signature]),
            "call_hash": self._stable_hash(called_functions),
            "dependency_hash": "",
        }

    @staticmethod
    def _signature_source(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        returns = ast.unparse(node.returns) if node.returns is not None else ""
        return f"{prefix} {node.name}({ast.unparse(node.args)}) -> {returns}"

    @staticmethod
    def _is_method_node(tree: ast.AST, target: ast.AST) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and target in node.body:
                return True
        return False

    @staticmethod
    def _stable_hash(parts: Iterable[str]) -> str:
        digest = hashlib.sha256()
        for part in parts:
            digest.update(part.encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()


class CallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: set[str] = set()

    def collect(self, node: ast.AST) -> set[str]:
        self.visit(node)
        return self.calls

    def visit_Call(self, node: ast.Call) -> None:
        name = self._call_name(node.func)
        if name:
            self.calls.add(name)
        self.generic_visit(node)

    def _call_name(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return None


class ImportCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports: list[dict[str, object]] = []

    def collect(self, node: ast.AST) -> list[dict[str, object]]:
        self.visit(node)
        return self.imports

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(
                {
                    "module": alias.name,
                    "name": None,
                    "alias": alias.asname,
                    "line": node.lineno,
                }
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            self.imports.append(
                {
                    "module": module,
                    "name": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                }
            )


def analyze_project_ast(project_path: Path, output_path: Path | None = None) -> Path:
    return AstAnalyzer().write_ast_index(project_path, output_path)
