"""Tools the code agent uses to walk a real repo.

Constraints:
- All paths are relative to ``repo_root``. Absolute paths and ``..``
  segments are rejected — the agent cannot escape the sandbox.
- A hardcoded ignore list (node_modules, .git, dist, build, .next,
  __pycache__, venv, .venv) is applied in ``list_directory``. We do not
  put this in the prompt — it is enforced.
- ``read_file`` truncates beyond ``max_bytes`` and returns a marker so the
  agent can tell.
- ``search_files`` is a simple regex grep across text files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.models import Evidence
from skene.llm.agent_loop import Tool
from skene.output import debug

IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {
        "node_modules",
        ".git",
        "dist",
        "build",
        ".next",
        "__pycache__",
        "venv",
        ".venv",
    }
)

_TEXT_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".md",
        ".txt",
        ".env",
        ".html",
        ".css",
        ".scss",
        ".sql",
        ".sh",
        ".rb",
        ".go",
        ".java",
        ".kt",
        ".rs",
        ".vue",
        ".svelte",
    }
)


class DirEntry(BaseModel):
    name: str
    is_dir: bool


class SearchHit(BaseModel):
    path: str
    line: int
    text: str = Field(min_length=1)


class FsToolset:
    """Bind to a single ``repo_root`` and a collector list."""

    def __init__(
        self,
        repo_root: Path,
        collector: list[CandidateMilestone],
        max_search_hits: int = 50,
    ) -> None:
        self._root = repo_root.resolve()
        if not self._root.exists() or not self._root.is_dir():
            raise FileNotFoundError(f"repo_root not found: {repo_root}")
        self._collector = collector
        self._max_search_hits = max_search_hits

    # --- Path safety ---

    def _resolve(self, rel: str) -> Path:
        """Return an absolute path inside ``_root`` or raise ValueError."""
        if not rel or rel in (".", "./"):
            return self._root
        p = Path(rel)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"path must be relative and inside the repo: {rel!r}")
        target = (self._root / p).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as e:
            raise ValueError(f"path escapes repo root: {rel!r}") from e
        return target

    # --- Internal implementations ---

    def _list_directory(self, path: str = ".") -> list[DirEntry] | dict[str, str]:
        try:
            target = self._resolve(path)
        except ValueError as e:
            return {"error": str(e)}
        if not target.exists():
            return {"error": f"path not found: {path!r}"}
        if not target.is_dir():
            return {"error": f"not a directory: {path!r}"}
        out: list[DirEntry] = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
            if child.is_dir() and child.name in IGNORED_DIR_NAMES:
                continue
            out.append(DirEntry(name=child.name, is_dir=child.is_dir()))
        return out

    def _read_file(self, path: str, max_bytes: int = 50_000) -> str | dict[str, str]:
        try:
            target = self._resolve(path)
        except ValueError as e:
            return {"error": str(e)}
        if not target.exists() or not target.is_file():
            return {"error": f"file not found: {path!r}"}
        try:
            data = target.read_bytes()
        except OSError as e:
            return {"error": f"could not read {path!r}: {e}"}
        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return {"error": f"binary file: {path!r}"}
        if truncated:
            text += f"\n\n[truncated at {max_bytes} bytes]"
        return text

    def _search_files(self, pattern: str, path: str = ".") -> list[SearchHit] | dict[str, str]:
        try:
            target = self._resolve(path)
        except ValueError as e:
            return {"error": str(e)}
        if not target.exists():
            return {"error": f"path not found: {path!r}"}
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return {"error": f"invalid regex: {e}"}

        hits: list[SearchHit] = []
        for fpath in self._walk_text_files(target):
            try:
                with fpath.open("r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if regex.search(line):
                            rel = str(fpath.relative_to(self._root))
                            text = line.rstrip("\n")[:240]
                            if not text:
                                text = "<match>"
                            hits.append(SearchHit(path=rel, line=lineno, text=text))
                            if len(hits) >= self._max_search_hits:
                                return hits
            except OSError:
                continue
        return hits

    def _walk_text_files(self, base: Path):
        if base.is_file():
            if base.suffix in _TEXT_SUFFIXES:
                yield base
            return
        for child in base.iterdir():
            if child.is_dir():
                if child.name in IGNORED_DIR_NAMES:
                    continue
                yield from self._walk_text_files(child)
            elif child.is_file() and child.suffix in _TEXT_SUFFIXES:
                yield child

    def _emit_milestone(
        self,
        proposed_id: str,
        name: str,
        description: str,
        path: str,
        reason: str,
        tracked_event: str | None = None,
        confidence: float = 0.8,
    ) -> str | dict[str, str]:
        try:
            target = self._resolve(path)
        except ValueError as e:
            return {"error": str(e)}
        if not target.exists() or not target.is_file():
            return {"error": (f"path {path!r} must be a real file you have read; use search_files / read_file first")}
        cm = CandidateMilestone(
            proposed_id=proposed_id,
            name=name,
            description=description,
            evidence=[Evidence(source="code", path=path, reason=reason)],
            tracked_event=tracked_event,
            confidence=confidence,
        )
        self._collector.append(cm)
        debug(f"fs tool: emit_milestone id={proposed_id} name={name!r} path={path} conf={confidence:.2f}")
        return f"recorded {proposed_id}"

    # --- Tool bindings ---

    def as_tools(self) -> list[Tool]:
        toolset = self

        def _dump_model(obj: Any) -> Any:
            if isinstance(obj, BaseModel):
                return obj.model_dump(mode="json")
            if isinstance(obj, list):
                return [_dump_model(x) for x in obj]
            return obj

        async def list_directory(args: dict[str, Any]) -> Any:
            path = args.get("path", ".")
            debug(f"fs tool: list_directory({path!r})")
            return _dump_model(toolset._list_directory(path))

        async def read_file(args: dict[str, Any]) -> Any:
            path = args["path"]
            max_bytes = int(args.get("max_bytes", 50_000))
            debug(f"fs tool: read_file({path!r}, max_bytes={max_bytes})")
            return _dump_model(toolset._read_file(path, max_bytes))

        async def search_files(args: dict[str, Any]) -> Any:
            pattern = args["pattern"]
            path = args.get("path", ".")
            debug(f"fs tool: search_files({pattern!r}, path={path!r})")
            return _dump_model(toolset._search_files(pattern, path))

        async def emit_milestone(args: dict[str, Any]) -> Any:
            return _dump_model(
                toolset._emit_milestone(
                    proposed_id=args["proposed_id"],
                    name=args["name"],
                    description=args["description"],
                    path=args["path"],
                    reason=args["reason"],
                    tracked_event=args.get("tracked_event"),
                    confidence=float(args.get("confidence", 0.8)),
                )
            )

        return [
            Tool(
                name="list_directory",
                description=(
                    "List entries in path (relative to repo root). Build, "
                    "dependency, and VCS dirs are filtered out automatically."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path. Defaults to repo root.",
                        }
                    },
                },
                handler=list_directory,
            ),
            Tool(
                name="read_file",
                description=(
                    "Read a text file. Truncates if larger than max_bytes and appends a [truncated ...] marker."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_bytes": {"type": "integer", "default": 50000},
                    },
                    "required": ["path"],
                },
                handler=read_file,
            ),
            Tool(
                name="search_files",
                description=("Regex search across text files under path. Returns up to 50 hits as {path, line, text}."),
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "path": {"type": "string", "default": "."},
                    },
                    "required": ["pattern"],
                },
                handler=search_files,
            ),
            Tool(
                name="emit_milestone",
                description=(
                    "Record a candidate milestone. path must point to a "
                    "real file inside the repo. The only way to produce output."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "proposed_id": {
                            "type": "string",
                            "description": "lowercase snake_case identifier",
                        },
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "path": {"type": "string"},
                        "reason": {"type": "string"},
                        "tracked_event": {"type": ["string", "null"]},
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                    "required": [
                        "proposed_id",
                        "name",
                        "description",
                        "path",
                        "reason",
                    ],
                },
                handler=emit_milestone,
            ),
        ]
