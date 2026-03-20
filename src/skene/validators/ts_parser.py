"""
Tree-sitter based source code name extraction (optional dependency).

Provides accurate extraction of function, class, and import names from
source files using tree-sitter grammars. Falls back gracefully when
tree-sitter or a specific language grammar is not installed.

Install the optional extras for tree-sitter support::

    pip install skene[ast]
"""

from __future__ import annotations

from pathlib import Path

from skene.validators.regex_parser import ExtractedNames

# ---------------------------------------------------------------------------
# Lazy imports — tree-sitter is optional
# ---------------------------------------------------------------------------

_ts_available: bool | None = None
_Parser: type | None = None
_Language: type | None = None


def _ensure_loaded() -> bool:
    """Attempt to import tree-sitter; cache the result."""
    global _ts_available, _Parser, _Language  # noqa: PLW0603
    if _ts_available is not None:
        return _ts_available
    try:
        from tree_sitter import Language as _L
        from tree_sitter import Parser as _P

        _Parser = _P
        _Language = _L
        _ts_available = True
    except ImportError:
        _ts_available = False
    return _ts_available


# Map file suffixes to (grammar-package-name, language-attr-or-callable).
# Each entry is (module_path, attribute_name_or_callable).
_GRAMMAR_MAP: dict[str, tuple[str, str | None]] = {
    ".js": ("tree_sitter_javascript", None),
    ".jsx": ("tree_sitter_javascript", None),
    ".mjs": ("tree_sitter_javascript", None),
    ".cjs": ("tree_sitter_javascript", None),
    ".ts": ("tree_sitter_typescript", "typescript"),
    ".tsx": ("tree_sitter_typescript", "tsx"),
}

_loaded_languages: dict[str, object] = {}


def _get_language(suffix: str) -> object | None:
    """Load and cache a tree-sitter Language for the given suffix."""
    suffix = suffix.lower()
    if suffix in _loaded_languages:
        return _loaded_languages[suffix]

    entry = _GRAMMAR_MAP.get(suffix)
    if entry is None:
        return None

    module_name, lang_attr = entry

    try:
        import importlib

        mod = importlib.import_module(module_name)

        if lang_attr is not None:
            lang_func = getattr(mod, lang_attr, None) or getattr(mod, "language", None)
        else:
            lang_func = getattr(mod, "language", None)

        if lang_func is None:
            return None

        if _Language is not None:
            lang = _Language(lang_func())
        else:
            return None

        _loaded_languages[suffix] = lang
        return lang
    except Exception:
        _loaded_languages[suffix] = None  # type: ignore[assignment]
        return None


def supported_suffix(suffix: str) -> bool:
    """Return True if tree-sitter can handle this file extension."""
    if not _ensure_loaded():
        return False
    return suffix.lower() in _GRAMMAR_MAP


# ---------------------------------------------------------------------------
# CST walking helpers
# ---------------------------------------------------------------------------


def _walk(node: object) -> list[object]:  # type: ignore[override]
    """Depth-first walk of all tree-sitter nodes."""
    cursor = node.walk()  # type: ignore[union-attr]
    nodes: list[object] = []

    reached_root = False
    while not reached_root:
        nodes.append(cursor.node)  # type: ignore[union-attr]
        if cursor.goto_first_child():  # type: ignore[union-attr]
            continue
        if cursor.goto_next_sibling():  # type: ignore[union-attr]
            continue
        retracing = True
        while retracing:
            if not cursor.goto_parent():  # type: ignore[union-attr]
                retracing = False
                reached_root = True
            elif cursor.goto_next_sibling():  # type: ignore[union-attr]
                retracing = False

    return nodes


def _child_by_field(node: object, field: str) -> object | None:
    return node.child_by_field_name(field)  # type: ignore[union-attr]


def _node_type(node: object) -> str:
    return node.type  # type: ignore[union-attr]


def _node_text(node: object, source: bytes) -> str:
    start = node.start_byte  # type: ignore[union-attr]
    end = node.end_byte  # type: ignore[union-attr]
    return source[start:end].decode("utf-8", errors="replace")


_FUNCTION_NODE_TYPES = frozenset(
    {
        "function_declaration",
        "method_definition",
        "generator_function_declaration",
    }
)

_ARROW_VAR_TYPES = frozenset(
    {
        "lexical_declaration",
        "variable_declaration",
        "export_statement",
    }
)

_CLASS_NODE_TYPES = frozenset(
    {
        "class_declaration",
        "interface_declaration",
        "type_alias_declaration",
        "enum_declaration",
        "abstract_class_declaration",
    }
)

_IMPORT_NODE_TYPES = frozenset(
    {
        "import_statement",
    }
)


def _extract_functions(nodes: list[object], source: bytes) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []

    for node in nodes:
        ntype = _node_type(node)

        if ntype in _FUNCTION_NODE_TYPES:
            name_node = _child_by_field(node, "name")
            if name_node:
                name = _node_text(name_node, source)
                if name not in seen:
                    seen.add(name)
                    names.append(name)

        elif ntype == "variable_declarator":
            name_node = _child_by_field(node, "name")
            value_node = _child_by_field(node, "value")
            if name_node and value_node and _node_type(value_node) in ("arrow_function", "function_expression"):
                name = _node_text(name_node, source)
                if name not in seen:
                    seen.add(name)
                    names.append(name)

    return names


def _extract_classes(nodes: list[object], source: bytes) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []

    for node in nodes:
        if _node_type(node) in _CLASS_NODE_TYPES:
            name_node = _child_by_field(node, "name")
            if name_node:
                name = _node_text(name_node, source)
                if name not in seen:
                    seen.add(name)
                    names.append(name)

    return names


def _extract_imports(nodes: list[object], source: bytes) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []

    for node in nodes:
        ntype = _node_type(node)

        # ES module imports: import ... from 'module'
        if ntype in _IMPORT_NODE_TYPES:
            source_node = _child_by_field(node, "source")
            if source_node:
                raw = _node_text(source_node, source).strip("'\"")
                if raw and raw not in seen:
                    seen.add(raw)
                    names.append(raw)

        # CommonJS require(): const x = require('module')
        elif ntype == "call_expression":
            func_node = _child_by_field(node, "function")
            if func_node and _node_text(func_node, source) == "require":
                args_node = _child_by_field(node, "arguments")
                if args_node:
                    for child in args_node.children:  # type: ignore[union-attr]
                        if _node_type(child) == "string":
                            raw = _node_text(child, source).strip("'\"")
                            if raw and raw not in seen:
                                seen.add(raw)
                                names.append(raw)
                            break

    return names


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_names(file_path: Path) -> ExtractedNames | None:
    """
    Extract function, class, and import names using tree-sitter.

    Returns ``None`` if tree-sitter is not installed, the language grammar
    is not available, or the file cannot be read.
    """
    if not _ensure_loaded() or _Parser is None:
        return None

    suffix = file_path.suffix.lower()
    lang = _get_language(suffix)
    if lang is None:
        return None

    try:
        source = file_path.read_bytes()
    except (OSError, UnicodeDecodeError):
        return None

    parser = _Parser()
    parser.language = lang  # type: ignore[assignment]
    tree = parser.parse(source)
    if tree is None or tree.root_node is None:
        return None

    nodes = _walk(tree.root_node)

    return ExtractedNames(
        functions=_extract_functions(nodes, source),
        classes=_extract_classes(nodes, source),
        imports=_extract_imports(nodes, source),
    )
