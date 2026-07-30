"""Ground-check synthesized evidence against the run's actual sources.

The subagents explore through sandboxed tools (``FsTools``,
``SchemaToolset``), but their final answer is generated JSON — a claim,
not a transcript of what they opened. ``Evidence.check_source_fields``
only enforces that ``source='code'`` carries a non-empty ``path`` and
``source='db'`` a non-empty ``table``; nothing resolves either against
the repo or the introspected schema. A plausible-looking fabricated
citation is therefore schema-valid and ships in ``journey.yaml`` at
whatever confidence the model self-reported.

This step closes that gap deterministically, with no extra LLM call:

- ``source='code'`` chips must name a path that exists inside
  ``repo_root`` (same relative/no-``..``/no-escape rules as
  ``FsTools._resolve``).
- ``source='db'`` chips must name a table the schema source actually
  contains (matched case-insensitively, ignoring schema qualification —
  agents cite ``public.users`` while introspection records ``users``).
- ``source='config'`` chips are checked like code chips when they carry
  a path, and kept as-is otherwise.

Chips that resolve to nothing are dropped, candidates left with no
evidence at all are dropped, and confidence is scaled by the fraction of
evidence that survived. Every check is opt-in: with ``repo_root=None``
code chips are not checked, and with ``known_tables=None`` db chips are
not checked, so callers without those sources see unchanged behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.models import Evidence, EvidenceSource


@dataclass
class GroundingReport:
    """What grounding removed, for the status line and for tests."""

    dropped_evidence: list[tuple[str, Evidence]] = field(default_factory=list)
    dropped_milestones: list[str] = field(default_factory=list)

    @property
    def evidence_count(self) -> int:
        return len(self.dropped_evidence)

    @property
    def milestone_count(self) -> int:
        return len(self.dropped_milestones)


def ground_candidates(
    candidates: list[CandidateMilestone],
    repo_root: Path | None = None,
    known_tables: set[str] | None = None,
) -> tuple[list[CandidateMilestone], GroundingReport]:
    """Drop evidence that does not resolve against the run's sources.

    Returns the surviving candidates plus a report of what was removed.
    Candidates whose evidence all failed grounding are removed entirely
    (an unproven milestone is not patched around), and the confidence of
    partially grounded candidates is scaled by the surviving fraction.
    """
    report = GroundingReport()
    if repo_root is None and known_tables is None:
        return candidates, report

    root = repo_root.resolve() if repo_root is not None else None
    table_names = {_normalize_table(t) for t in known_tables} if known_tables is not None else None

    kept_candidates: list[CandidateMilestone] = []
    for cm in candidates:
        kept: list[Evidence] = []
        for ev in cm.evidence:
            if _is_grounded(ev, root, table_names):
                kept.append(ev)
            else:
                report.dropped_evidence.append((cm.proposed_id, ev))
        if not kept:
            report.dropped_milestones.append(cm.proposed_id)
            continue
        if len(kept) < len(cm.evidence):
            scale = len(kept) / len(cm.evidence)
            cm = cm.model_copy(
                update={
                    "evidence": kept,
                    "confidence": round(cm.confidence * scale, 4),
                }
            )
        kept_candidates.append(cm)
    return kept_candidates, report


def _is_grounded(ev: Evidence, root: Path | None, table_names: set[str] | None) -> bool:
    if ev.source == EvidenceSource.db:
        if table_names is None or ev.table is None:
            return True
        return _normalize_table(ev.table) in table_names
    # code always carries a path (model-enforced); config only sometimes.
    if ev.path is None or root is None:
        return True
    return _path_exists_in_root(root, ev.path)


def _normalize_table(name: str) -> str:
    """Case-fold and strip schema qualification (``public.users`` → ``users``)."""
    return name.lower().rsplit(".", 1)[-1]


def _path_exists_in_root(root: Path, rel: str) -> bool:
    """Same containment rules as ``FsTools._resolve``, plus existence."""
    if not rel or rel in (".", "./"):
        return True
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        return False
    try:
        target = (root / p).resolve()
        target.relative_to(root)
    except (ValueError, OSError):
        return False
    return target.exists()
