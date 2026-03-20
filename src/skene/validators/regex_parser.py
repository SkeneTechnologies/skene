"""
Regex-based source code name extraction for non-Python languages.

Provides best-effort extraction of function, class, and import names
from source files using language-aware regular expressions. This serves
as the always-available fallback when tree-sitter is not installed.

Supported language families:
- JavaScript / TypeScript (.js, .jsx, .ts, .tsx, .mjs, .cjs)
- Java (.java)
- Go (.go)
- Ruby (.rb)
- Rust (.rs)
- PHP (.php)
- C# (.cs)
- Kotlin (.kt, .kts)
- Swift (.swift)
- Dart (.dart)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtractedNames:
    """Names extracted from a source file."""

    functions: list[str]
    classes: list[str]
    imports: list[str]


_LANG_BY_SUFFIX: dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".php": "php",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".dart": "dart",
}

# ---------------------------------------------------------------------------
# Language-specific regex patterns
# ---------------------------------------------------------------------------

# JS / TS ----------------------------------------------------------------

_JS_FUNCTION_PATTERNS = [
    re.compile(r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)"),
    re.compile(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>"),
    re.compile(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function"),
    re.compile(r"^\s+(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*\S+)?\s*\{", re.MULTILINE),
    re.compile(r"(?:public|private|protected|static)\s+(?:async\s+)?(\w+)\s*\("),
]

_JS_CLASS_PATTERNS = [
    re.compile(r"(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)"),
    re.compile(r"(?:export\s+)?(?:default\s+)?interface\s+(\w+)"),
    re.compile(r"(?:export\s+)?(?:default\s+)?type\s+(\w+)\s*(?:=|<)"),
    re.compile(r"(?:export\s+)?enum\s+(\w+)"),
]

_JS_IMPORT_PATTERNS = [
    re.compile(r"""import\s+(?:type\s+)?(?:\{[^}]*\}|[*]\s+as\s+\w+|\w+)\s+from\s+['"]([^'"]+)['"]"""),
    re.compile(r"""import\s+['"]([^'"]+)['"]"""),
    re.compile(r"""(?:const|let|var)\s+\w+\s*=\s*require\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
]

# Java -------------------------------------------------------------------

_JAVA_FUNCTION_PATTERNS = [
    re.compile(
        r"(?:public|private|protected|static|\s)*\s+"
        r"(?:\w+(?:<[^>]*(?:<[^>]*>[^>]*)?>)?)\s+"
        r"(\w+)\s*\("
    ),
]

_JAVA_CLASS_PATTERNS = [
    re.compile(r"(?:public|private|protected|abstract|final|\s)*\s*class\s+(\w+)"),
    re.compile(r"(?:public|private|protected|\s)*\s*interface\s+(\w+)"),
    re.compile(r"(?:public|private|protected|\s)*\s*enum\s+(\w+)"),
    re.compile(r"(?:public|private|protected|\s)*\s*record\s+(\w+)"),
]

_JAVA_IMPORT_PATTERNS = [
    re.compile(r"import\s+(?:static\s+)?([a-zA-Z0-9_.]+)\s*;"),
]

# Go ---------------------------------------------------------------------

_GO_FUNCTION_PATTERNS = [
    re.compile(r"func\s+(?:\([^)]*\)\s+)?(\w+)\s*\("),
]

_GO_CLASS_PATTERNS = [
    re.compile(r"type\s+(\w+)\s+struct\b"),
    re.compile(r"type\s+(\w+)\s+interface\b"),
]

_GO_IMPORT_PATTERNS = [
    re.compile(r"""import\s+"([^"]+)"""),
    re.compile(r"""\s+"([^"]+)"""),  # inside import blocks
]

# Ruby -------------------------------------------------------------------

_RUBY_FUNCTION_PATTERNS = [
    re.compile(r"def\s+(?:self\.)?(\w+[!?]?)"),
]

_RUBY_CLASS_PATTERNS = [
    re.compile(r"class\s+(\w+)"),
    re.compile(r"module\s+(\w+)"),
]

_RUBY_IMPORT_PATTERNS = [
    re.compile(r"""require\s+['"]([^'"]+)['"]"""),
    re.compile(r"""require_relative\s+['"]([^'"]+)['"]"""),
    re.compile(r"include\s+(\w+)"),
]

# Rust -------------------------------------------------------------------

_RUST_FUNCTION_PATTERNS = [
    re.compile(r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)"),
]

_RUST_CLASS_PATTERNS = [
    re.compile(r"(?:pub\s+)?struct\s+(\w+)"),
    re.compile(r"(?:pub\s+)?enum\s+(\w+)"),
    re.compile(r"(?:pub\s+)?trait\s+(\w+)"),
    re.compile(r"impl(?:<[^>]*>)?\s+(\w+)"),
]

_RUST_IMPORT_PATTERNS = [
    re.compile(r"use\s+([a-zA-Z0-9_:]+)"),
    re.compile(r"extern\s+crate\s+(\w+)"),
]

# PHP --------------------------------------------------------------------

_PHP_FUNCTION_PATTERNS = [
    re.compile(r"(?:public|private|protected|static|\s)*\s*function\s+(\w+)\s*\("),
]

_PHP_CLASS_PATTERNS = [
    re.compile(r"(?:abstract\s+)?class\s+(\w+)"),
    re.compile(r"interface\s+(\w+)"),
    re.compile(r"trait\s+(\w+)"),
    re.compile(r"enum\s+(\w+)"),
]

_PHP_IMPORT_PATTERNS = [
    re.compile(r"use\s+([a-zA-Z0-9_\\]+)"),
    re.compile(r"""(?:include|require)(?:_once)?\s+['"]([^'"]+)['"]"""),
]

# C# ---------------------------------------------------------------------

_CS_FUNCTION_PATTERNS = [
    re.compile(
        r"(?:public|private|protected|internal|static|async|virtual|override|abstract|\s)*\s+"
        r"(?:\w+(?:<[^>]*(?:<[^>]*>[^>]*)?>)?)\s+"
        r"(\w+)\s*\("
    ),
]

_CS_CLASS_PATTERNS = [
    re.compile(r"(?:public|private|protected|internal|abstract|sealed|static|\s)*\s*class\s+(\w+)"),
    re.compile(r"(?:public|private|protected|internal|\s)*\s*interface\s+(\w+)"),
    re.compile(r"(?:public|private|protected|internal|\s)*\s*enum\s+(\w+)"),
    re.compile(r"(?:public|private|protected|internal|\s)*\s*record\s+(\w+)"),
    re.compile(r"(?:public|private|protected|internal|\s)*\s*struct\s+(\w+)"),
]

_CS_IMPORT_PATTERNS = [
    re.compile(r"using\s+(?:static\s+)?([a-zA-Z0-9_.]+)\s*;"),
]

# Kotlin -----------------------------------------------------------------

_KT_FUNCTION_PATTERNS = [
    re.compile(r"(?:(?:public|private|protected|internal|override|suspend)\s+)*fun\s+(?:<[^>]*>\s+)?(\w+)\s*\("),
]

_KT_CLASS_PATTERNS = [
    re.compile(r"(?:(?:data|sealed|abstract|open|inner)\s+)*class\s+(\w+)"),
    re.compile(r"(?:fun\s+)?interface\s+(\w+)"),
    re.compile(r"enum\s+class\s+(\w+)"),
    re.compile(r"object\s+(\w+)"),
]

_KT_IMPORT_PATTERNS = [
    re.compile(r"import\s+([a-zA-Z0-9_.]+)"),
]

# Swift ------------------------------------------------------------------

_SWIFT_FUNCTION_PATTERNS = [
    re.compile(r"(?:(?:public|private|internal|fileprivate|open|static|class|override)\s+)*func\s+(\w+)"),
]

_SWIFT_CLASS_PATTERNS = [
    re.compile(r"(?:(?:public|private|internal|fileprivate|open|final)\s+)*class\s+(\w+)"),
    re.compile(r"(?:(?:public|private|internal|fileprivate)\s+)*struct\s+(\w+)"),
    re.compile(r"(?:(?:public|private|internal|fileprivate)\s+)*protocol\s+(\w+)"),
    re.compile(r"(?:(?:public|private|internal|fileprivate)\s+)*enum\s+(\w+)"),
]

_SWIFT_IMPORT_PATTERNS = [
    re.compile(r"import\s+(\w+)"),
]

# Dart -------------------------------------------------------------------

_DART_FUNCTION_PATTERNS = [
    re.compile(r"(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*\("),
    re.compile(r"void\s+(\w+)\s*\("),
]

_DART_CLASS_PATTERNS = [
    re.compile(r"(?:abstract\s+)?class\s+(\w+)"),
    re.compile(r"mixin\s+(\w+)"),
    re.compile(r"enum\s+(\w+)"),
    re.compile(r"extension\s+(\w+)"),
]

_DART_IMPORT_PATTERNS = [
    re.compile(r"""import\s+['"]([^'"]+)['"]"""),
    re.compile(r"""export\s+['"]([^'"]+)['"]"""),
]

# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, tuple[list[re.Pattern[str]], list[re.Pattern[str]], list[re.Pattern[str]]]] = {
    "javascript": (_JS_FUNCTION_PATTERNS, _JS_CLASS_PATTERNS, _JS_IMPORT_PATTERNS),
    "typescript": (_JS_FUNCTION_PATTERNS, _JS_CLASS_PATTERNS, _JS_IMPORT_PATTERNS),
    "java": (_JAVA_FUNCTION_PATTERNS, _JAVA_CLASS_PATTERNS, _JAVA_IMPORT_PATTERNS),
    "go": (_GO_FUNCTION_PATTERNS, _GO_CLASS_PATTERNS, _GO_IMPORT_PATTERNS),
    "ruby": (_RUBY_FUNCTION_PATTERNS, _RUBY_CLASS_PATTERNS, _RUBY_IMPORT_PATTERNS),
    "rust": (_RUST_FUNCTION_PATTERNS, _RUST_CLASS_PATTERNS, _RUST_IMPORT_PATTERNS),
    "php": (_PHP_FUNCTION_PATTERNS, _PHP_CLASS_PATTERNS, _PHP_IMPORT_PATTERNS),
    "csharp": (_CS_FUNCTION_PATTERNS, _CS_CLASS_PATTERNS, _CS_IMPORT_PATTERNS),
    "kotlin": (_KT_FUNCTION_PATTERNS, _KT_CLASS_PATTERNS, _KT_IMPORT_PATTERNS),
    "swift": (_SWIFT_FUNCTION_PATTERNS, _SWIFT_CLASS_PATTERNS, _SWIFT_IMPORT_PATTERNS),
    "dart": (_DART_FUNCTION_PATTERNS, _DART_CLASS_PATTERNS, _DART_IMPORT_PATTERNS),
}


def supported_suffix(suffix: str) -> bool:
    """Return True if the file extension is supported by regex extraction."""
    return suffix.lower() in _LANG_BY_SUFFIX


def _strip_comments(content: str, lang: str) -> str:
    """Remove line and block comments to avoid false positives in commented-out code."""
    if lang in ("ruby",):
        content = re.sub(r"#[^\n]*", "", content)
        content = re.sub(r"=begin.*?=end", "", content, flags=re.DOTALL)
    else:
        content = re.sub(r"//[^\n]*", "", content)
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    return content


def _extract_with_patterns(
    content: str, patterns: list[re.Pattern[str]]
) -> list[str]:
    """Run all patterns against content and return unique ordered matches."""
    seen: set[str] = set()
    names: list[str] = []
    for pat in patterns:
        for m in pat.finditer(content):
            name = m.group(1)
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def extract_names(file_path: Path) -> ExtractedNames | None:
    """
    Extract function, class, and import names from a source file using regex.

    Returns ``None`` if the file extension is not supported or the file
    cannot be read.
    """
    suffix = file_path.suffix.lower()
    lang = _LANG_BY_SUFFIX.get(suffix)
    if lang is None:
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    cleaned = _strip_comments(content, lang)
    func_pats, class_pats, import_pats = _PATTERNS[lang]

    return ExtractedNames(
        functions=_extract_with_patterns(cleaned, func_pats),
        classes=_extract_with_patterns(cleaned, class_pats),
        imports=_extract_with_patterns(content, import_pats),  # imports from raw content
    )
