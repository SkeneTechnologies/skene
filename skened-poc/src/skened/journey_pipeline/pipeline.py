"""Pipeline orchestrator + the daemon ``Analyzer`` adapter.

Flow (mirrors analyze-journey, minus the LLM by default):

    extract candidates → merge/dedup → classify into stages → assemble validated Journey

Both the extractor and the classifier are injectable seams (see ``extract.py`` /
``classify.py`` / ``llm.py``), so migrating to an LLM backend is a constructor change.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from typing import Protocol

from ..analyzer import AnalysisContext
from ..journey import Evidence, EvidenceSource, Journey
from .assemble import assemble_journey
from .candidate import CandidateMilestone
from .classify import Classifier, HeuristicClassifier
from .extract import CandidateExtractor, HeuristicCodeScanner
from .merge import merge_candidates

logger = logging.getLogger("skened.pipeline")


class Brancher(Protocol):
    async def branch(
        self,
        *,
        base_journey: Journey,
        changed_paths: set[str],
        removed_paths: set[str],
        diff_text: str,
        branch_worktree: Path,
        product_name: str,
        base_branch: str,
        source_commit: str | None,
        generated_at: datetime | None,
    ) -> Journey: ...


class JourneyPipeline:
    def __init__(
        self,
        extractor: CandidateExtractor | None = None,
        classifier: Classifier | None = None,
        brancher: Brancher | None = None,
    ) -> None:
        self.extractor: CandidateExtractor = extractor or HeuristicCodeScanner()
        self.classifier: Classifier = classifier or HeuristicClassifier()
        # When set, branch analysis uses this LLM brancher; otherwise the deterministic diff.
        self.brancher: Brancher | None = brancher

    async def run(
        self,
        repo_root: Path,
        product_name: str,
        *,
        source_commit: str | None = None,
        branch: str | None = None,
        generated_at: datetime | None = None,
    ) -> Journey:
        generated_at = generated_at or datetime.now(timezone.utc)
        candidates = await self.extractor.extract(repo_root)
        merged = merge_candidates(candidates)

        if not merged:
            # Robustness: never fail a branch analysis on a sparse repo. Emit a single
            # baseline discovery milestone so the daemon always gets a valid Journey.
            merged = [_baseline_candidate(repo_root)]

        classified = await self.classifier.classify(merged)
        description = _describe(branch, len(classified))
        return assemble_journey(
            classified, product_name,
            generated_at=generated_at, source_commit=source_commit,
            product_description=description,
        )

    async def branch_from(
        self,
        base_journey: Journey,
        branch_worktree: Path,
        *,
        changed_paths: set[str],
        removed_paths: set[str],
        product_name: str,
        base_branch: str,
        source_commit: str | None = None,
        generated_at: datetime | None = None,
        diff_text: str = "",
    ) -> Journey:
        """Derive a branch's journey FROM the default branch's journey.

        If an LLM ``brancher`` is configured, it reads the base journey + the code diff and
        returns the branch's journey. Otherwise the deterministic differ runs:

        - Milestones whose evidence does not touch a changed/removed file are kept verbatim.
        - Changed/added files are re-analyzed; their fresh milestones replace/augment the base.
        - Milestones whose only evidence was a removed file simply drop out.

        With no journey-relevant changes, the result equals the base journey.
        """
        generated_at = generated_at or datetime.now(timezone.utc)

        # With the LLM backend, the brancher IS the branch analysis — its errors propagate
        # and fail the run. The deterministic differ below is the heuristic backend, used
        # only when no brancher is configured (not a fallback).
        if self.brancher is not None:
            return await self.brancher.branch(
                base_journey=base_journey,
                changed_paths=set(changed_paths),
                removed_paths=set(removed_paths),
                diff_text=diff_text,
                branch_worktree=branch_worktree,
                product_name=product_name,
                base_branch=base_branch,
                source_commit=source_commit,
                generated_at=generated_at,
            )

        touched = set(changed_paths) | set(removed_paths)

        base_candidates = candidates_from_journey(base_journey)
        kept = [c for c in base_candidates if not _touches(c, touched)]

        fresh: list[CandidateMilestone] = []
        if changed_paths:
            extracted = await self.extractor.extract(branch_worktree, only_paths=set(changed_paths))
            fresh = await self.classifier.classify(extracted)

        # Fresh (branch) candidates first so they win on any id/name collision.
        final = merge_candidates(fresh, kept)
        if not final:
            final = [_baseline_candidate(branch_worktree)]

        n_changed, n_removed = len(changed_paths), len(removed_paths)
        if not touched:
            description = f"Branched from '{base_branch}' analysis — no journey-relevant code changes."
        else:
            description = (
                f"Branched from '{base_branch}' analysis — "
                f"{n_changed} changed / {n_removed} removed file(s)."
            )
        return assemble_journey(
            final, product_name,
            generated_at=generated_at, source_commit=source_commit,
            product_description=description,
        )


class JourneyPipelineAnalyzer:
    """Adapts ``JourneyPipeline`` to the daemon's ``Analyzer`` protocol."""

    def __init__(self, pipeline: JourneyPipeline | None = None) -> None:
        self.pipeline = pipeline or JourneyPipeline()

    async def analyze(self, ctx: AnalysisContext) -> Journey:
        return await self.pipeline.run(
            ctx.worktree_path,
            product_name=ctx.project_name,
            source_commit=ctx.commit,
            branch=ctx.branch,
        )


def candidates_from_journey(journey: Journey) -> list[CandidateMilestone]:
    """Reconstruct classified candidates from an assembled journey (for branching)."""
    out: list[CandidateMilestone] = []
    for stage in journey.stages:
        for m in stage.milestones:
            out.append(CandidateMilestone(
                proposed_id=m.id,
                name=m.name,
                description=m.description,
                evidence=list(m.evidence),
                tracked_event=m.tracked_event,
                confidence=m.confidence,
                stage_id=stage.id,
            ))
    return out


def _touches(candidate: CandidateMilestone, paths: set[str]) -> bool:
    return any(ev.path in paths for ev in candidate.evidence if ev.path)


def _describe(branch: str | None, n: int) -> str:
    where = f" for branch '{branch}'" if branch else ""
    return f"Journey map generated by the heuristic code pipeline{where} ({n} milestone(s))."


def _baseline_candidate(repo_root: Path) -> CandidateMilestone:
    preferred = ("README.md", "README", "pyproject.toml", "package.json", "main.py", "index.js")
    path = next((n for n in preferred if (repo_root / n).exists()), None)
    if path is None:
        try:
            path = next((p.name for p in sorted(Path(repo_root).iterdir()) if p.is_file()), "README.md")
        except OSError:
            path = "README.md"
    return CandidateMilestone(
        proposed_id="entry_point",
        name="Entry point",
        description="Baseline milestone — the analysis produced no other milestones for this "
                    "branch (e.g. a sparse repo, or a branch that removes most of the product).",
        evidence=[Evidence(source=EvidenceSource.code, path=path,
                           reason="Representative repo file (no other milestones).")],
        confidence=0.2,
        # Pre-classified so the branch fallbacks (which skip the classifier) can assemble it.
        stage_id="discovery",
    )
