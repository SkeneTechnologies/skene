"""Analysis seam.

``Analyzer`` is the single seam the analysis engine plugs into: given an
``AnalysisContext`` (a worktree checked out at a commit), return a ``Journey``. The
daemon's default implementation is ``JourneyPipelineAnalyzer`` in ``journey_pipeline``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .journey import Journey


@dataclass(frozen=True)
class AnalysisContext:
    project_name: str
    branch: str
    commit: str
    worktree_path: Path


class Analyzer(Protocol):
    async def analyze(self, ctx: AnalysisContext) -> Journey: ...
