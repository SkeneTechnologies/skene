"""Tree-sitter based JS/TS parser implementing the ParsedTree protocol."""

from __future__ import annotations

from pathlib import Path

from skene.output import debug

# Lazy-loaded language objects
_languages: dict[str, object] = {}


def _get_language(suffix: str):
    """Return the tree-sitter Language for the given file suffix."""
    import tree_sitter_javascript as tsjs
    import tree_sitter_typescript as tsts
    from tree_sitter import Language

    if suffix not in _languages:
        if suffix in (".js", ".mjs", ".jsx"):
            _languages[suffix] = Language(tsjs.language())
        elif suffix in (".ts", ".mts"):
            _languages[suffix] = Language(tsts.language_typescript())
        elif suffix == ".tsx":
            _languages[suffix] = Language(tsts.language_tsx())
    return _languages.get(suffix)


def _get_parser(suffix: str):
    """Return a tree-sitter Parser configured for the given file suffix."""
    from tree_sitter import Parser

    lang = _get_language(suffix)
    if lang is None:
        return None
    parser = Parser(lang)
    return parser


class TSParsedTree:
    """ParsedTree implementation backed by tree-sitter for JS/TS files."""

    def __init__(self, tree, source: bytes, file_path: Path) -> None:
        self._tree = tree
        self._source = source
        self._file_path = file_path

    def function_names(self) -> list[str]:
        names: list[str] = []
        self._walk_functions(self._tree.root_node, names)
        return names

    def _walk_functions(self, node, names: list[str]) -> None:
        """Recursively collect function names from the tree."""
        # function_declaration: function foo() {}
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                names.append(name_node.text.decode("utf-8"))

        # generator_function_declaration: function* foo() {}
        elif node.type == "generator_function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                names.append(name_node.text.decode("utf-8"))

        # method_definition inside class body
        elif node.type == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                names.append(name_node.text.decode("utf-8"))

        # Variable declarator with arrow function or function expression:
        # const foo = () => {} or const foo = function() {}
        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node and value_node and value_node.type in (
                "arrow_function",
                "function_expression",
            ):
                names.append(name_node.text.decode("utf-8"))

        # export_statement: export function foo() {} or export default function foo() {}
        elif node.type == "export_statement":
            for child in node.children:
                if child.type in ("function_declaration", "generator_function_declaration"):
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        names.append(name_node.text.decode("utf-8"))
                    return  # already handled, skip recursion into this child
                elif child.type == "lexical_declaration":
                    # export const foo = () => {}
                    for decl in child.children:
                        if decl.type == "variable_declarator":
                            name_node = decl.child_by_field_name("name")
                            value_node = decl.child_by_field_name("value")
                            if name_node and value_node and value_node.type in (
                                "arrow_function",
                                "function_expression",
                            ):
                                names.append(name_node.text.decode("utf-8"))
                    return

        # Recurse into children
        for child in node.children:
            self._walk_functions(child, names)

    def class_names(self) -> list[str]:
        names: list[str] = []
        self._walk_classes(self._tree.root_node, names)
        return names

    def _walk_classes(self, node, names: list[str]) -> None:
        """Recursively collect class and interface names."""
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                names.append(name_node.text.decode("utf-8"))

        elif node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                names.append(name_node.text.decode("utf-8"))

        elif node.type == "export_statement":
            for child in node.children:
                if child.type in ("class_declaration", "interface_declaration"):
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        names.append(name_node.text.decode("utf-8"))
                    return

        for child in node.children:
            self._walk_classes(child, names)

    def import_names(self) -> list[str]:
        names: list[str] = []
        self._walk_imports(self._tree.root_node, names)
        return names

    def _walk_imports(self, node, names: list[str]) -> None:
        """Collect import source strings from ESM imports and CommonJS require."""
        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node:
                module_name = source_node.text.decode("utf-8").strip("'\"")
                names.append(module_name)
                # Add dotted names for named imports: import { X } from "mod" -> "mod.X"
                for child in node.children:
                    if child.type == "import_clause":
                        self._extract_import_specifiers(child, module_name, names)

        elif node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node and func_node.text.decode("utf-8") == "require":
                args_node = node.child_by_field_name("arguments")
                if args_node and args_node.child_count > 0:
                    for arg in args_node.children:
                        if arg.type == "string":
                            module_name = arg.text.decode("utf-8").strip("'\"")
                            names.append(module_name)

        for child in node.children:
            self._walk_imports(child, names)

    def _extract_import_specifiers(self, clause_node, module_name: str, names: list[str]) -> None:
        """Extract named import specifiers from an import clause."""
        for child in clause_node.children:
            if child.type == "named_imports":
                for spec in child.children:
                    if spec.type == "import_specifier":
                        name_node = spec.child_by_field_name("name")
                        if name_node:
                            names.append(f"{module_name}.{name_node.text.decode('utf-8')}")
            elif child.type == "identifier":
                # default import: import Foo from "mod" -> "mod.Foo"
                names.append(f"{module_name}.{child.text.decode('utf-8')}")
            elif child.type == "namespace_import":
                # import * as X from "mod" -> "mod.X"
                for sub in child.children:
                    if sub.type == "identifier":
                        names.append(f"{module_name}.{sub.text.decode('utf-8')}")

    def function_signature(self, func_name: str) -> str | None:
        return self._find_signature(self._tree.root_node, func_name)

    def _find_signature(self, node, func_name: str) -> str | None:
        """Recursively search for a function's signature."""
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node and name_node.text.decode("utf-8") == func_name:
                return _extract_ts_signature(node, self._source)

        elif node.type == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node and name_node.text.decode("utf-8") == func_name:
                return _extract_ts_signature(node, self._source)

        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if (
                name_node
                and name_node.text.decode("utf-8") == func_name
                and value_node
                and value_node.type in ("arrow_function", "function_expression")
            ):
                return _extract_ts_signature_from_arrow(func_name, value_node, self._source)

        elif node.type == "export_statement":
            for child in node.children:
                if child.type == "function_declaration":
                    name_node = child.child_by_field_name("name")
                    if name_node and name_node.text.decode("utf-8") == func_name:
                        return _extract_ts_signature(child, self._source)
                elif child.type == "lexical_declaration":
                    for decl in child.children:
                        result = self._find_signature(decl, func_name)
                        if result is not None:
                            return result

        for child in node.children:
            result = self._find_signature(child, func_name)
            if result is not None:
                return result
        return None

    def function_infos(self) -> list:
        from skene.validators.loop_validator import FunctionInfo

        source_lines = self._source.decode("utf-8").splitlines()
        infos: list[FunctionInfo] = []
        self._collect_function_infos(self._tree.root_node, source_lines, infos)
        return infos

    def _collect_function_infos(self, node, source_lines: list[str], infos: list) -> None:
        from skene.validators.loop_validator import FunctionInfo

        name: str | None = None
        sig: str | None = None
        line_no = 0

        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8")
                sig = _extract_ts_signature(node, self._source)
                line_no = node.start_point[0] + 1

        elif node.type == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8")
                sig = _extract_ts_signature(node, self._source)
                line_no = node.start_point[0] + 1

        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node and value_node and value_node.type in ("arrow_function", "function_expression"):
                name = name_node.text.decode("utf-8")
                sig = _extract_ts_signature_from_arrow(name, value_node, self._source)
                line_no = node.start_point[0] + 1

        elif node.type == "export_statement":
            for child in node.children:
                if child.type in ("function_declaration", "lexical_declaration", "class_declaration"):
                    self._collect_function_infos(child, source_lines, infos)
            return

        if name and sig:
            start = line_no - 1
            end = min(start + 20, len(source_lines))
            source_snippet = "\n".join(source_lines[start:end])
            infos.append(
                FunctionInfo(
                    file_path=str(self._file_path),
                    name=name,
                    signature=sig,
                    docstring="",
                    line_number=line_no,
                    source_code=source_snippet,
                )
            )

        for child in node.children:
            self._collect_function_infos(child, source_lines, infos)


def _extract_ts_signature(node, source: bytes) -> str:
    """Extract a human-readable signature from a function/method node."""
    name_node = node.child_by_field_name("name")
    name = name_node.text.decode("utf-8") if name_node else "anonymous"

    params_node = node.child_by_field_name("parameters")
    params_text = params_node.text.decode("utf-8") if params_node else "()"

    # Look for return type annotation
    return_type = ""
    for child in node.children:
        if child.type == "type_annotation":
            return_type = child.text.decode("utf-8").lstrip(": ").strip()
            break

    ret_str = f" -> {return_type}" if return_type else ""
    return f"{name}{params_text}{ret_str}"


def _extract_ts_signature_from_arrow(name: str, value_node, source: bytes) -> str:
    """Extract a signature from an arrow function or function expression."""
    params_node = value_node.child_by_field_name("parameters")
    if params_node:
        params_text = params_node.text.decode("utf-8")
    else:
        # Single parameter without parens: x => ...
        for child in value_node.children:
            if child.type == "identifier" and child == value_node.children[0]:
                params_text = f"({child.text.decode('utf-8')})"
                break
        else:
            params_text = "()"

    # Look for return type annotation
    return_type = ""
    for child in value_node.children:
        if child.type == "type_annotation":
            return_type = child.text.decode("utf-8").lstrip(": ").strip()
            break

    ret_str = f" -> {return_type}" if return_type else ""
    return f"{name}{params_text}{ret_str}"


def parse_js_ts(file_path: Path) -> TSParsedTree | None:
    """Parse a JS/TS file and return a TSParsedTree, or None on failure."""
    try:
        source = file_path.read_bytes()
    except OSError as exc:
        debug(f"Could not read {file_path}: {exc}")
        return None

    parser = _get_parser(file_path.suffix)
    if parser is None:
        debug(f"No tree-sitter parser for suffix {file_path.suffix}")
        return None

    try:
        tree = parser.parse(source)
    except Exception as exc:
        debug(f"tree-sitter parse failed for {file_path}: {exc}")
        return None

    return TSParsedTree(tree, source, file_path)
