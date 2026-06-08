"""Filesystem tools the LLM code agent uses to explore a repo (sandboxed to repo_root).

Mirrors the reference toolset: ``list_directory``, ``read_file``, ``search_files`` and the
``emit_milestone`` sink. All paths are relative to ``repo_root``; ``..`` and absolute paths
are rejected so the agent cannot escape the worktree.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..journey import Evidence, EvidenceSource
from .agent_loop import Tool
from .candidate import CandidateMilestone
from .extract import IGNORED_DIR_NAMES, TEXT_SUFFIXES, _slugify

MAX_SEARCH_HITS = 50
DEFAULT_READ_BYTES = 50_000


class FsTools:
    def __init__(self, repo_root: Path, collector: list[CandidateMilestone]) -> None:
        self._root = Path(repo_root).resolve()
        self._collector = collector

    # --- path safety ---------------------------------------------------------
    def _resolve(self, rel: str) -> Path:
        if not rel or rel in (".", "./"):
            return self._root
        p = Path(rel)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"path must be relative and inside the repo: {rel!r}")
        target = (self._root / p).resolve()
        target.relative_to(self._root)  # raises ValueError if it escapes
        return target

    # --- tool implementations ------------------------------------------------
    def list_directory(self, path: str = ".") -> Any:
        target = self._resolve(path)
        if not target.is_dir():
            return {"error": f"not a directory: {path!r}"}
        out = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
            if child.is_dir() and child.name in IGNORED_DIR_NAMES:
                continue
            out.append({"name": child.name, "is_dir": child.is_dir()})
        return out

    def read_file(self, path: str, max_bytes: int = DEFAULT_READ_BYTES) -> Any:
        target = self._resolve(path)
        if not target.is_file():
            return {"error": f"file not found: {path!r}"}
        data = target.read_bytes()
        text = data[:max_bytes].decode(errors="ignore")
        if len(data) > max_bytes:
            text += f"\n... [truncated at {max_bytes} bytes]"
        return text

    def search_files(self, pattern: str, path: str = ".") -> Any:
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return {"error": f"bad regex: {e}"}
        root = self._resolve(path)
        hits: list[dict] = []
        for f in self._iter_text_files(root):
            try:
                for i, line in enumerate(f.read_text(errors="ignore").splitlines(), start=1):
                    if rx.search(line):
                        hits.append({"path": str(f.relative_to(self._root)), "line": i, "text": line.strip()[:200]})
                        if len(hits) >= MAX_SEARCH_HITS:
                            return hits
            except OSError:
                continue
        return hits

    def emit_milestone(
        self,
        proposed_id: str,
        name: str,
        description: str,
        path: str,
        reason: str,
        tracked_event: str | None = None,
        confidence: float = 0.8,
    ) -> Any:
        cm = CandidateMilestone(
            proposed_id=_slugify(proposed_id),
            name=name,
            description=description,
            evidence=[Evidence(source=EvidenceSource.code, path=path, reason=reason)],
            tracked_event=tracked_event,
            confidence=max(0.0, min(1.0, confidence)),
        )
        self._collector.append(cm)
        return {"ok": True, "id": cm.proposed_id}

    def _iter_text_files(self, root: Path):
        import os
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIR_NAMES and not d.startswith(".")]
            for n in filenames:
                p = Path(dirpath) / n
                if p.suffix.lower() in TEXT_SUFFIXES:
                    yield p

    # --- tool schemas --------------------------------------------------------
    def as_tools(self) -> list[Tool]:
        return [
            Tool("list_directory", "List files and directories at a repo-relative path.",
                 {"type": "object", "properties": {"path": {"type": "string"}}},
                 self.list_directory),
            Tool("read_file", "Read a repo-relative text file (truncated at max_bytes).",
                 {"type": "object",
                  "properties": {"path": {"type": "string"}, "max_bytes": {"type": "integer"}},
                  "required": ["path"]},
                 self.read_file),
            Tool("search_files", "Regex-search text files under a repo-relative path. Returns up to 50 hits.",
                 {"type": "object",
                  "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
                  "required": ["pattern"]},
                 self.search_files),
            Tool("emit_milestone",
                 "Record a candidate user-journey milestone backed by a code path. Do NOT classify into a stage.",
                 {"type": "object",
                  "properties": {
                      "proposed_id": {"type": "string", "description": "lowercase snake_case"},
                      "name": {"type": "string"},
                      "description": {"type": "string"},
                      "path": {"type": "string", "description": "repo-relative file you read/searched"},
                      "reason": {"type": "string"},
                      "tracked_event": {"type": "string"},
                      "confidence": {"type": "number"},
                  },
                  "required": ["proposed_id", "name", "description", "path", "reason"]},
                 self.emit_milestone),
        ]
