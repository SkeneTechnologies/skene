"""
Multi-language growth loop requirement validator.

Validates that code requirements defined in growth loop JSON files
are actually implemented in the codebase by:
- Checking file existence
- Parsing source code to verify function/class/import definitions
  (Python via ``ast``, JS/TS via tree-sitter or regex, other languages via regex)
- Searching file content for required patterns
- Tracking telemetry events for validation lifecycle

Designed for modular integration into a CLI ``watch`` command.
"""

from __future__ import annotations

import ast
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from skene.growth_loops.storage import load_existing_growth_loops
from skene.output import console, debug, warning
from skene.validators import regex_parser as _regex
from skene.validators import ts_parser as _treesitter
from skene.validators.regex_parser import ExtractedNames

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class CheckStatus(str, Enum):
    """Result status for a single requirement check."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Result of validating a single requirement check."""

    check_type: str
    pattern: str
    description: str
    status: CheckStatus
    detail: str = ""


@dataclass
class FileValidationResult:
    """Aggregated result for a single file requirement."""

    path: str
    purpose: str
    required: bool
    exists: bool
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        if self.required and not self.exists:
            return False
        return all(c.status == CheckStatus.PASSED for c in self.checks)


@dataclass
class AlternativeMatch:
    """An existing function that might fulfill a requirement."""

    file_path: str
    function_name: str
    signature: str
    confidence: float
    reasoning: str = ""


@dataclass
class FunctionValidationResult:
    """Result of validating a function requirement."""

    file_path: str
    name: str
    required: bool
    expected_signature: str
    found: bool
    signature_match: bool
    detail: str = ""
    alternatives: list[AlternativeMatch] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        if self.required and not self.found:
            return False
        return self.found


@dataclass
class LoopValidationResult:
    """Aggregated validation result for a complete growth loop."""

    loop_id: str
    loop_name: str
    source_file: str
    file_results: list[FileValidationResult] = field(default_factory=list)
    function_results: list[FunctionValidationResult] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def all_passed(self) -> bool:
        files_ok = all(r.passed for r in self.file_results)
        funcs_ok = all(r.passed for r in self.function_results)
        return files_ok and funcs_ok

    @property
    def total_checks(self) -> int:
        return len(self.file_results) + len(self.function_results)

    @property
    def passed_checks(self) -> int:
        passed = sum(1 for r in self.file_results if r.passed)
        passed += sum(1 for r in self.function_results if r.passed)
        return passed


# ---------------------------------------------------------------------------
# Telemetry / event hooks
# ---------------------------------------------------------------------------


class ValidationEvent(str, Enum):
    """Events emitted during the validation lifecycle."""

    LOOP_VALIDATION_STARTED = "loop_validation_started"
    REQUIREMENT_MET = "requirement_met"
    LOOP_COMPLETED = "loop_completed"
    VALIDATION_TIME = "validation_time"


# Global listener registry — external code (CLI, watch mode) can subscribe.
_event_listeners: list[Callable[[ValidationEvent, dict[str, Any]], None]] = []


def register_event_listener(
    callback: Callable[[ValidationEvent, dict[str, Any]], None],
) -> None:
    """Register a callback for validation events."""
    _event_listeners.append(callback)


def clear_event_listeners() -> None:
    """Remove all registered event listeners."""
    _event_listeners.clear()


def _emit(event: ValidationEvent, payload: dict[str, Any]) -> None:
    """Emit a validation event to all registered listeners."""
    for listener in _event_listeners:
        try:
            listener(event, payload)
        except Exception as exc:  # noqa: BLE001
            warning(f"Event listener error for {event.value}: {exc}")


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


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
    """
    Extract a human-readable signature string for *func_name*.

    Returns ``None`` if the function is not found.
    """
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


# ---------------------------------------------------------------------------
# Multi-language name extraction
# ---------------------------------------------------------------------------

# Extensions that are handled by the Python ``ast`` module.
_PYTHON_SUFFIXES = frozenset({".py", ".pyi"})

# All extensions with any level of extraction support (Python + regex + tree-sitter).
_ALL_SUPPORTED_SUFFIXES = _PYTHON_SUFFIXES | frozenset(_regex._LANG_BY_SUFFIX.keys())


def _extract_names_python(file_path: Path) -> ExtractedNames | None:
    """Extract names from a Python file using the built-in ``ast`` module."""
    tree = _parse_ast(file_path)
    if tree is None:
        return None
    return ExtractedNames(
        functions=ast_function_names(tree),
        classes=ast_class_names(tree),
        imports=ast_import_names(tree),
    )


def _extract_names(file_path: Path) -> ExtractedNames | None:
    """
    Extract function, class, and import names from a source file.

    Resolution order:
    1. Python ``ast`` module for ``.py`` / ``.pyi`` files.
    2. Tree-sitter (if installed) for JS/TS and other supported grammars.
    3. Regex-based extraction as the always-available fallback.

    Returns ``None`` only when the file extension is completely unsupported
    or the file cannot be read.
    """
    suffix = file_path.suffix.lower()

    if suffix in _PYTHON_SUFFIXES:
        return _extract_names_python(file_path)

    # Try tree-sitter first (more accurate).
    if _treesitter.supported_suffix(suffix):
        result = _treesitter.extract_names(file_path)
        if result is not None:
            debug(f"Extracted names via tree-sitter for {file_path}")
            return result

    # Regex fallback (always available for known languages).
    if _regex.supported_suffix(suffix):
        result = _regex.extract_names(file_path)
        if result is not None:
            debug(f"Extracted names via regex for {file_path}")
            return result

    return None


# ---------------------------------------------------------------------------
# Codebase function extraction (for finding alternatives)
# ---------------------------------------------------------------------------


@dataclass
class FunctionInfo:
    """Information about a function extracted from the codebase."""

    file_path: str
    name: str
    signature: str
    docstring: str
    line_number: int
    source_code: str = ""


def extract_all_functions(project_root: Path, exclude_dirs: list[str] | None = None) -> list[FunctionInfo]:
    """
    Extract all function definitions from source files in the project.

    Scans Python files via the ``ast`` module and other supported languages
    (JS, TS, etc.) via tree-sitter or regex extraction.

    Args:
        project_root: Root directory of the project
        exclude_dirs: List of directory names to exclude (e.g., ['venv', '.git'])

    Returns:
        List of FunctionInfo objects for all functions found
    """
    if exclude_dirs is None:
        exclude_dirs = ["venv", ".venv", "__pycache__", ".git", "node_modules", ".pytest_cache"]

    functions: list[FunctionInfo] = []

    # --- Python files (rich AST with signatures & docstrings) ---
    for py_file in project_root.rglob("*.py"):
        if any(excluded in str(py_file) for excluded in exclude_dirs):
            continue
        try:
            if py_file.stat().st_size > 1_000_000:
                continue
        except OSError:
            continue

        tree = _parse_ast(py_file)
        if tree is None:
            continue

        rel_path = str(py_file.relative_to(project_root))

        try:
            source_lines = py_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            source_lines = []

        for node in ast.walk(tree):
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
                        file_path=rel_path,
                        name=node.name,
                        signature=sig,
                        docstring=docstring,
                        line_number=node.lineno if hasattr(node, "lineno") else 0,
                        source_code=source_snippet,
                    )
                )

    # --- Non-Python files (tree-sitter / regex, names only) ---
    non_py_globs = ["*.ts", "*.tsx", "*.js", "*.jsx", "*.mjs", "*.go", "*.java", "*.rb", "*.rs", "*.php"]
    for glob in non_py_globs:
        for src_file in project_root.rglob(glob):
            if any(excluded in str(src_file) for excluded in exclude_dirs):
                continue
            try:
                if src_file.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue

            names = _extract_names(src_file)
            if names is None:
                continue

            rel_path = str(src_file.relative_to(project_root))
            for func_name in names.functions:
                functions.append(
                    FunctionInfo(
                        file_path=rel_path,
                        name=func_name,
                        signature=func_name,
                        docstring="",
                        line_number=0,
                    )
                )

    return functions


async def find_semantic_matches(
    requirement: dict[str, Any],
    candidate_functions: list[FunctionInfo],
    llm_client: Any,  # LLMClient
    max_candidates: int = 20,
) -> list[AlternativeMatch]:
    """
    Use LLM to find existing functions that might fulfill a requirement.

    Args:
        requirement: Function requirement dict from growth loop JSON
        candidate_functions: List of all functions in the codebase
        llm_client: LLM client for semantic analysis (optional, can be None)
        max_candidates: Maximum number of candidates to send to LLM

    Returns:
        List of AlternativeMatch objects, sorted by confidence (highest first)
    """
    if not llm_client or not candidate_functions:
        return []

    req_name = requirement.get("name", "")
    req_signature = requirement.get("signature", "")
    req_logic = requirement.get("logic", "")
    req_file = requirement.get("file", "")

    # Filter: skip test files, dunder methods, and private helpers — prioritise source code
    filtered = [
        f
        for f in candidate_functions
        if not f.file_path.startswith("tests/")
        and not f.name.startswith("test_")
        and f.name != "__init__"
        and not f.name.startswith("__")
    ]

    # Limit candidates to avoid token limits
    candidates = filtered[:max_candidates]

    # Build prompt for LLM
    candidates_json = []
    for func in candidates:
        candidates_json.append(
            {
                "file": func.file_path,
                "name": func.name,
                "signature": func.signature,
                "docstring": func.docstring[:200] if func.docstring else "",
                "source_preview": func.source_code[:500] if func.source_code else "",
            }
        )

    debug(f"Searching for alternatives to '{req_name}' ({len(candidates)} candidates)")

    prompt = f"""You are analyzing code requirements. A growth loop requires a function with these specifications:

**Required Function:**
- Name: {req_name}
- Expected Signature: {req_signature}
- Expected Location: {req_file}
- Required Logic: {req_logic}

**Existing Functions in Codebase:**
{json.dumps(candidates_json, indent=2)}

**Task:**
Analyze each existing function and determine if it could fulfill the requirement. Consider:
1. Does the function do what's required (based on name, docstring, signature)?
2. Could it be adapted or is it already suitable?
3. What's the confidence level (0.0 to 1.0)?

Return a JSON array of matches, each with:
- "file": file path
- "function_name": function name
- "signature": function signature
- "confidence": float between 0.0 and 1.0
- "reasoning": brief explanation

Only include matches with confidence >= 0.6. Return empty array [] if no good matches.

Return ONLY valid JSON, no markdown, no explanations."""

    try:
        response = await llm_client.generate_content(prompt)
        response = response.strip()

        # Clean up response - remove markdown code fences if present
        if response.startswith("```"):
            lines = response.split("\n")
            start_idx = 0
            end_idx = len(lines)
            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    if start_idx == 0:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            response = "\n".join(lines[start_idx:end_idx])

        matches_data = json.loads(response)
        if not isinstance(matches_data, list):
            return []

        matches: list[AlternativeMatch] = []
        for match_data in matches_data:
            if isinstance(match_data, dict) and match_data.get("confidence", 0) >= 0.6:
                matches.append(
                    AlternativeMatch(
                        file_path=match_data.get("file", ""),
                        function_name=match_data.get("function_name", ""),
                        signature=match_data.get("signature", ""),
                        confidence=float(match_data.get("confidence", 0)),
                        reasoning=match_data.get("reasoning", ""),
                    )
                )

        # Sort by confidence (highest first)
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches

    except Exception as exc:
        debug(f"LLM semantic matching failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Check normalisation (handles both dict and legacy string formats)
# ---------------------------------------------------------------------------

_LEGACY_CHECK_RE = re.compile(
    r"^(contains_pattern|function_exists|defines_class|contains_logic|class_exists|import_exists)"
    r"\('([^']+)'\)$"
)

_LEGACY_TYPE_MAP = {
    "contains_pattern": "contains_regex",
    "contains_logic": "contains",
    "function_exists": "function_exists",
    "defines_class": "class_exists",
    "class_exists": "class_exists",
    "import_exists": "import_exists",
}


@dataclass
class NormalisedCheck:
    """A check normalised from either dict or string format."""

    check_type: str  # contains | contains_regex | function_exists | class_exists | import_exists
    pattern: str
    description: str


def normalise_check(raw: dict | str) -> NormalisedCheck:
    """
    Normalise a check entry from either format found in growth loop JSONs.

    Dict format (preferred):
        {"type": "function_exists", "pattern": "scan_for_leaks", "description": "..."}

    Legacy string format:
        "function_exists('scan_for_leaks')"
    """
    if isinstance(raw, dict):
        return NormalisedCheck(
            check_type=raw.get("type", "contains"),
            pattern=raw.get("pattern", ""),
            description=raw.get("description", ""),
        )

    # Legacy string format
    match = _LEGACY_CHECK_RE.match(raw.strip())
    if match:
        raw_type, pattern = match.group(1), match.group(2)
        check_type = _LEGACY_TYPE_MAP.get(raw_type, "contains")
        return NormalisedCheck(
            check_type=check_type,
            pattern=pattern,
            description=f"{check_type}: {pattern}",
        )

    # Fallback — treat entire string as a contains pattern
    return NormalisedCheck(
        check_type="contains",
        pattern=raw.strip(),
        description=f"contains: {raw.strip()}",
    )


# ---------------------------------------------------------------------------
# Individual check runners
# ---------------------------------------------------------------------------


def _run_contains_check(
    file_path: Path,
    pattern: str,
    description: str,
) -> CheckResult:
    """Check whether *file_path* contains a literal substring *pattern*."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CheckResult("contains", pattern, description, CheckStatus.FAILED, str(exc))

    if pattern in content:
        return CheckResult("contains", pattern, description, CheckStatus.PASSED)
    return CheckResult("contains", pattern, description, CheckStatus.FAILED, "Pattern not found in file")


def _run_contains_regex_check(
    file_path: Path,
    pattern: str,
    description: str,
) -> CheckResult:
    """Check whether *file_path* matches a regex *pattern*."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CheckResult("contains_regex", pattern, description, CheckStatus.FAILED, str(exc))

    try:
        if re.search(pattern, content):
            return CheckResult("contains_regex", pattern, description, CheckStatus.PASSED)
        return CheckResult("contains_regex", pattern, description, CheckStatus.FAILED, "Regex did not match")
    except re.error as exc:
        return CheckResult("contains_regex", pattern, description, CheckStatus.FAILED, f"Invalid regex: {exc}")


def _run_function_exists_check(
    names: ExtractedNames | None,
    file_path: Path,
    pattern: str,
    description: str,
) -> CheckResult:
    """Check whether a function named *pattern* exists in the extracted names."""
    if names is None:
        suffix = file_path.suffix
        return CheckResult(
            "function_exists",
            pattern,
            description,
            CheckStatus.SKIPPED,
            f"Code parsing not supported for '{suffix}' files; use 'contains' or 'contains_regex' instead",
        )
    if pattern in names.functions:
        return CheckResult("function_exists", pattern, description, CheckStatus.PASSED)
    return CheckResult("function_exists", pattern, description, CheckStatus.FAILED, f"Function '{pattern}' not found")


def _run_class_exists_check(
    names: ExtractedNames | None,
    file_path: Path,
    pattern: str,
    description: str,
) -> CheckResult:
    """Check whether a class named *pattern* exists in the extracted names."""
    if names is None:
        suffix = file_path.suffix
        return CheckResult(
            "class_exists",
            pattern,
            description,
            CheckStatus.SKIPPED,
            f"Code parsing not supported for '{suffix}' files; use 'contains' or 'contains_regex' instead",
        )
    if pattern in names.classes:
        return CheckResult("class_exists", pattern, description, CheckStatus.PASSED)
    return CheckResult("class_exists", pattern, description, CheckStatus.FAILED, f"Class '{pattern}' not found")


def _run_import_exists_check(
    names: ExtractedNames | None,
    file_path: Path,
    pattern: str,
    description: str,
) -> CheckResult:
    """Check whether an import matching *pattern* exists in the extracted names."""
    if names is None:
        suffix = file_path.suffix
        return CheckResult(
            "import_exists",
            pattern,
            description,
            CheckStatus.SKIPPED,
            f"Code parsing not supported for '{suffix}' files; use 'contains' or 'contains_regex' instead",
        )

    for name in names.imports:
        if pattern in name or name.endswith(pattern):
            return CheckResult("import_exists", pattern, description, CheckStatus.PASSED)

    return CheckResult("import_exists", pattern, description, CheckStatus.FAILED, f"Import '{pattern}' not found")


_CHECK_RUNNERS: dict[str, Callable[..., CheckResult]] = {
    "contains": lambda fp, names, pat, desc: _run_contains_check(fp, pat, desc),
    "contains_regex": lambda fp, names, pat, desc: _run_contains_regex_check(fp, pat, desc),
    "function_exists": lambda fp, names, pat, desc: _run_function_exists_check(names, fp, pat, desc),
    "class_exists": lambda fp, names, pat, desc: _run_class_exists_check(names, fp, pat, desc),
    "import_exists": lambda fp, names, pat, desc: _run_import_exists_check(names, fp, pat, desc),
}


# ---------------------------------------------------------------------------
# High-level validation
# ---------------------------------------------------------------------------


def _resolve_file_path(requirement_path: str, project_root: Path) -> Path:
    """Resolve a requirement file path relative to the project root."""
    return (project_root / requirement_path).resolve()


def validate_file_requirement(
    file_req: dict[str, Any],
    project_root: Path,
) -> FileValidationResult:
    """Validate a single file requirement entry from the growth loop JSON."""
    rel_path = file_req.get("path", "")
    purpose = file_req.get("purpose", "")
    required = file_req.get("required", True)
    raw_checks = file_req.get("checks", [])

    abs_path = _resolve_file_path(rel_path, project_root)
    exists = abs_path.is_file()

    result = FileValidationResult(
        path=rel_path,
        purpose=purpose,
        required=required,
        exists=exists,
    )

    if not exists:
        # If file doesn't exist, all checks fail
        for raw in raw_checks:
            nc = normalise_check(raw)
            result.checks.append(
                CheckResult(nc.check_type, nc.pattern, nc.description, CheckStatus.FAILED, "File does not exist")
            )
        return result

    # Extract names once for all AST-style checks on this file.
    # _extract_names handles Python, tree-sitter, and regex fallback automatically.
    needs_names = any(
        (normalise_check(r).check_type in ("function_exists", "class_exists", "import_exists")) for r in raw_checks
    )
    names = _extract_names(abs_path) if needs_names else None

    for raw in raw_checks:
        nc = normalise_check(raw)
        runner = _CHECK_RUNNERS.get(nc.check_type)
        if runner:
            check_result = runner(abs_path, names, nc.pattern, nc.description)
        else:
            check_result = CheckResult(
                nc.check_type,
                nc.pattern,
                nc.description,
                CheckStatus.SKIPPED,
                f"Unknown check type: {nc.check_type}",
            )
        result.checks.append(check_result)

    return result


async def validate_function_requirement(
    func_req: dict[str, Any],
    project_root: Path,
    all_functions: list[FunctionInfo] | None = None,
    llm_client: Any | None = None,
) -> FunctionValidationResult:
    """Validate a single function requirement entry from the growth loop JSON."""
    file_rel = func_req.get("file", "")
    name = func_req.get("name", "")
    required = func_req.get("required", True)
    expected_sig = func_req.get("signature", "")

    abs_path = _resolve_file_path(file_rel, project_root)
    found = False
    sig_match = False
    detail = ""
    alternatives: list[AlternativeMatch] = []

    if not abs_path.is_file():
        detail = "File does not exist"
    else:
        names = _extract_names(abs_path)
        if names is None:
            suffix = abs_path.suffix
            if suffix.lower() in _PYTHON_SUFFIXES:
                detail = "Could not parse Python file AST"
            else:
                detail = (
                    f"Code parsing not supported for '{suffix}' files; "
                    "use 'contains' or 'contains_regex' checks instead"
                )
        else:
            found = name in names.functions

            if found and expected_sig and abs_path.suffix.lower() in _PYTHON_SUFFIXES:
                # Signature matching only available for Python via ast
                tree = _parse_ast(abs_path)
                if tree is not None:
                    actual_sig = ast_function_signature(tree, name)
                    if actual_sig:
                        norm_expected = re.sub(r"\s+", " ", expected_sig.strip())
                        norm_actual = re.sub(r"\s+", " ", actual_sig.strip())
                        sig_match = norm_expected == norm_actual
                        if not sig_match:
                            detail = f"Signature mismatch: expected '{norm_expected}', got '{norm_actual}'"
                    else:
                        detail = "Function found but could not extract signature"
                else:
                    sig_match = True
            elif found:
                sig_match = True

    # If function not found, try to find semantic matches in the entire codebase
    if not found and all_functions and llm_client:
        try:
            alternatives = await find_semantic_matches(func_req, all_functions, llm_client)
        except Exception as exc:
            debug(f"Failed to find semantic matches: {exc}")

    return FunctionValidationResult(
        file_path=file_rel,
        name=name,
        required=required,
        expected_signature=expected_sig,
        found=found,
        signature_match=sig_match,
        detail=detail,
        alternatives=alternatives,
    )


async def validate_growth_loop(
    loop_data: dict[str, Any],
    project_root: Path,
    all_functions: list[FunctionInfo] | None = None,
    llm_client: Any | None = None,
) -> LoopValidationResult:
    """
    Validate all requirements for a single growth loop definition.

    Emits telemetry events during the process.
    """
    loop_id = loop_data.get("loop_id", "unknown")
    loop_name = loop_data.get("name", "Unnamed Loop")
    source_file = loop_data.get("_source_file", "")

    _emit(
        ValidationEvent.LOOP_VALIDATION_STARTED,
        {
            "loop_id": loop_id,
            "loop_name": loop_name,
        },
    )

    start = time.perf_counter()
    requirements = loop_data.get("requirements", {})

    result = LoopValidationResult(
        loop_id=loop_id,
        loop_name=loop_name,
        source_file=source_file,
    )

    # --- File requirements ---
    for file_req in requirements.get("files", []):
        fv = validate_file_requirement(file_req, project_root)
        result.file_results.append(fv)
        if fv.passed:
            _emit(
                ValidationEvent.REQUIREMENT_MET,
                {
                    "loop_id": loop_id,
                    "type": "file",
                    "path": fv.path,
                },
            )

    # --- Function requirements ---
    for func_req in requirements.get("functions", []):
        fv = await validate_function_requirement(func_req, project_root, all_functions, llm_client)
        result.function_results.append(fv)
        if fv.passed:
            _emit(
                ValidationEvent.REQUIREMENT_MET,
                {
                    "loop_id": loop_id,
                    "type": "function",
                    "name": fv.name,
                    "file": fv.file_path,
                },
            )

    elapsed = (time.perf_counter() - start) * 1000
    result.elapsed_ms = elapsed

    _emit(
        ValidationEvent.VALIDATION_TIME,
        {
            "loop_id": loop_id,
            "elapsed_ms": round(elapsed, 2),
        },
    )

    if result.all_passed:
        _emit(
            ValidationEvent.LOOP_COMPLETED,
            {
                "loop_id": loop_id,
                "loop_name": loop_name,
                "total_checks": result.total_checks,
            },
        )

    return result


async def validate_all_loops(
    context_dir: Path,
    project_root: Path,
    llm_client: Any | None = None,
    find_alternatives: bool = False,
) -> list[LoopValidationResult]:
    """
    Load and validate every growth loop JSON in *context_dir*/growth-loops/.

    Args:
        context_dir: Path to the skene-context directory.
        project_root: Root of the project codebase.

    Returns:
        List of validation results, one per loop.
    """
    loops = load_existing_growth_loops(context_dir)
    if not loops:
        debug(f"No growth loop definitions found in {context_dir / 'growth-loops'}")
        return []

    # Extract all functions from codebase if we need to find alternatives
    all_functions: list[FunctionInfo] | None = None
    if find_alternatives and llm_client:
        debug("Extracting all functions from codebase for semantic matching...")
        all_functions = extract_all_functions(project_root)
        debug(f"Found {len(all_functions)} functions in codebase")

    results: list[LoopValidationResult] = []
    for loop_data in loops:
        result = await validate_growth_loop(loop_data, project_root, all_functions, llm_client)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Console reporting
# ---------------------------------------------------------------------------

_STATUS_ICON = {
    CheckStatus.PASSED: "[green]✅[/green]",
    CheckStatus.FAILED: "[red]❌[/red]",
    CheckStatus.SKIPPED: "[yellow]⏭️[/yellow]",
}


def print_validation_report(results: list[LoopValidationResult]) -> None:
    """Print a Rich-formatted validation report to the console.

    Uses the shared console from output.py for all rendering.
    """
    if not results:
        warning("No growth loops found to validate.")
        return

    total_loops = len(results)
    completed_loops = sum(1 for r in results if r.all_passed)

    console.print()
    console.print(
        Panel(
            f"[bold]Growth Loop Validation[/bold]  —  {completed_loops}/{total_loops} loops complete",
            style="cyan",
        )
    )

    for result in results:
        _print_loop_result(result, console)

    # Summary
    console.print()
    if completed_loops == total_loops:
        console.print("[bold green]All growth loops fully implemented![/bold green]")
    else:
        pending = total_loops - completed_loops
        console.print(f"[bold yellow]{pending} loop(s) have unmet requirements.[/bold yellow]")


def _print_loop_result(
    result: LoopValidationResult,
    console: Any,
) -> None:
    """Print detailed results for a single loop."""
    loop_status = "[green]COMPLETE[/green]" if result.all_passed else "[red]INCOMPLETE[/red]"
    header = Text.from_markup(
        f"[bold]{result.loop_name}[/bold] ({result.loop_id})  {loop_status}"
        f"[dim]({result.passed_checks}/{result.total_checks} checks, {result.elapsed_ms:.0f}ms)[/dim]"
    )
    console.print(header)

    if result.all_passed:
        console.print("")
        console.print(f"   [green]✅ GROWTH LOOP COMPLETE: {result.loop_name}[/green]")
        console.print("")
        return

    # File requirements table
    if result.file_results:
        table = Table(show_header=True, header_style="bold", padding=(0, 1), expand=False)
        table.add_column("", width=3)
        table.add_column("File", style="cyan", no_wrap=True)
        table.add_column("Status")
        table.add_column("Detail", style="dim")

        for fr in result.file_results:
            icon = _STATUS_ICON[CheckStatus.PASSED] if fr.passed else _STATUS_ICON[CheckStatus.FAILED]
            status_text = "Exists" if fr.exists else "Missing"

            details: list[str] = []
            if not fr.exists:
                details.append("File not found")
            for cr in fr.checks:
                if cr.status != CheckStatus.PASSED:
                    details.append(f"{cr.check_type}('{cr.pattern}'): {cr.detail or 'failed'}")

            table.add_row(icon, fr.path, status_text, "; ".join(details) if details else "OK")

        console.print(table)

    # Function requirements table
    if result.function_results:
        table = Table(show_header=True, header_style="bold", padding=(0, 1), expand=False)
        table.add_column("", width=3)
        table.add_column("Function", style="cyan", no_wrap=True)
        table.add_column("File", style="dim")
        table.add_column("Detail", style="dim")

        for fv in result.function_results:
            icon = _STATUS_ICON[CheckStatus.PASSED] if fv.passed else _STATUS_ICON[CheckStatus.FAILED]
            detail = fv.detail if fv.detail else ("Found" if fv.found else "Missing")

            # Add alternative matches info if available
            if fv.alternatives:
                alt_info = f"{detail} | 💡 {len(fv.alternatives)} alternative(s) found"
                table.add_row(icon, fv.name, fv.file_path, alt_info)
            else:
                table.add_row(icon, fv.name, fv.file_path, detail)

        console.print(table)

        # Show alternative matches after the table
        for fv in result.function_results:
            if fv.alternatives:
                console.print(f"    [dim]💡 Alternatives for '{fv.name}':[/dim]")
                for alt in fv.alternatives[:3]:  # Show top 3
                    console.print(
                        f"      • [cyan]{alt.function_name}[/cyan] in [dim]{alt.file_path}[/dim] "
                        f"({alt.confidence:.0%} match)"
                    )
                    if alt.reasoning:
                        console.print(f"        [dim]{alt.reasoning[:100]}[/dim]")
                if len(fv.alternatives) > 3:
                    console.print(f"      [dim]... and {len(fv.alternatives) - 3} more[/dim]")

    console.print()
