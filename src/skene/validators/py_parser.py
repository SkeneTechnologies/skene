"""Python AST parser implementing the ParsedTree protocol."""

from __future__ import annotations

import ast
from pathlib import Path

from skene.output import debug


def _parse_ast(file_path: Path) -> ast.Module | None:
    """Parse a Python file into an AST, returning *None* on failure."""
    try:
        source = file_path.read_text(encoding="utf-8")
        return ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError) as exc:
        debug(f"AST parse failed for {file_path}: {exc}")
        return None


def ast_function_names(tree: ast.Module) -> list[str]:
    """Return all top-level and class-level function/method names."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
    return names


def ast_class_names(tree: ast.Module) -> list[str]:
    """Return all class names defined in the module."""
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def ast_import_names(tree: ast.Module) -> list[str]:
    """Return all imported names (both ``import X`` and ``from X import Y``)."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append(module)
            for alias in node.names:
                names.append(f"{module}.{alias.name}" if module else alias.name)
    return names


def ast_function_signature(tree: ast.Module, func_name: str) -> str | None:
    """Extract a human-readable signature string for *func_name*."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return _format_signature(node)
    return None


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Format an AST function node into a readable signature."""
    params: list[str] = []
    args = node.args

    # Positional args
    defaults_offset = len(args.args) - len(args.defaults)
    for i, arg in enumerate(args.args):
        if arg.arg == "self":
            continue
        annotation = _annotation_str(arg.annotation)
        param = f"{arg.arg}: {annotation}" if annotation else arg.arg
        default_idx = i - defaults_offset
        if default_idx >= 0 and args.defaults[default_idx]:
            param += " = ..."
        params.append(param)

    # *args
    if args.vararg:
        annotation = _annotation_str(args.vararg.annotation)
        params.append(f"*{args.vararg.arg}: {annotation}" if annotation else f"*{args.vararg.arg}")

    # **kwargs
    if args.kwarg:
        annotation = _annotation_str(args.kwarg.annotation)
        params.append(f"**{args.kwarg.arg}: {annotation}" if annotation else f"**{args.kwarg.arg}")

    ret = _annotation_str(node.returns)
    ret_str = f" -> {ret}" if ret else ""
    return f"{node.name}({', '.join(params)}){ret_str}"


def _annotation_str(node: ast.expr | None) -> str:
    """Best-effort string representation of a type annotation AST node."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


class PythonParsedTree:
    """ParsedTree implementation backed by Python's built-in ``ast`` module."""

    def __init__(self, tree: ast.Module, file_path: Path) -> None:
        self._tree = tree
        self._file_path = file_path

    def function_names(self) -> list[str]:
        return ast_function_names(self._tree)

    def class_names(self) -> list[str]:
        return ast_class_names(self._tree)

    def import_names(self) -> list[str]:
        return ast_import_names(self._tree)

    def function_signature(self, func_name: str) -> str | None:
        return ast_function_signature(self._tree, func_name)

    def function_infos(self) -> list:
        from skene.validators.loop_validator import FunctionInfo

        try:
            source_lines = self._file_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            source_lines = []

        functions: list[FunctionInfo] = []
        for node in ast.walk(self._tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = _format_signature(node)
                docstring = ast.get_docstring(node) or ""

                source_snippet = ""
                if source_lines and hasattr(node, "lineno"):
                    start_line = node.lineno - 1
                    end_line = min(start_line + 20, len(source_lines))
                    source_snippet = "\n".join(source_lines[start_line:end_line])

                functions.append(
                    FunctionInfo(
                        file_path=str(self._file_path),
                        name=node.name,
                        signature=sig,
                        docstring=docstring,
                        line_number=node.lineno if hasattr(node, "lineno") else 0,
                        source_code=source_snippet,
                    )
                )
        return functions


def parse_python(file_path: Path) -> PythonParsedTree | None:
    """Parse a Python file and return a PythonParsedTree, or None on failure."""
    tree = _parse_ast(file_path)
    if tree is None:
        return None
    return PythonParsedTree(tree, file_path)
