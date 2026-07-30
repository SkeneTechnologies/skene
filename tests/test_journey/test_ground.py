"""Tests for ground_candidates (evidence grounding before assembly)."""

from __future__ import annotations

from pathlib import Path

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.ground import ground_candidates
from skene.analyzers.journey.models import Evidence


def _candidate(
    pid: str,
    evidence: list[Evidence],
    *,
    confidence: float = 0.9,
    stage_id: str = "onboarding",
) -> CandidateMilestone:
    return CandidateMilestone(
        proposed_id=pid,
        name=pid,
        description=pid,
        evidence=evidence,
        confidence=confidence,
        stage_id=stage_id,
    )


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "src" / "auth").mkdir(parents=True)
    (tmp_path / "src" / "auth" / "signup.py").write_text("def signup(): ...\n")
    return tmp_path


def test_hallucinated_code_path_is_dropped_and_confidence_scaled(tmp_path):
    root = _repo(tmp_path)
    cm = _candidate(
        "signup",
        [
            Evidence(source="code", path="src/auth/signup.py", reason="real"),
            Evidence(source="code", path="src/auth/does_not_exist.py", reason="ghost"),
        ],
        confidence=0.95,
    )
    kept, report = ground_candidates([cm], repo_root=root)
    assert len(kept) == 1
    assert [ev.path for ev in kept[0].evidence] == ["src/auth/signup.py"]
    assert kept[0].confidence == 0.475  # 0.95 * 1/2
    assert report.evidence_count == 1
    assert report.milestone_count == 0


def test_milestone_with_only_ghost_evidence_is_dropped(tmp_path):
    root = _repo(tmp_path)
    cm = _candidate(
        "phantom",
        [Evidence(source="code", path="src/never/was.py", reason="ghost")],
    )
    kept, report = ground_candidates([cm], repo_root=root)
    assert kept == []
    assert report.milestone_count == 1
    assert report.dropped_milestones == ["phantom"]


def test_db_table_checked_against_introspected_schema(tmp_path):
    real = _candidate("orders", [Evidence(source="db", table="Orders", reason="row")])
    qualified = _candidate("users", [Evidence(source="db", table="public.users", reason="row")])
    ghost = _candidate("ghosts", [Evidence(source="db", table="unicorns", reason="row")])
    kept, report = ground_candidates([real, qualified, ghost], known_tables={"orders", "users"})
    assert [c.proposed_id for c in kept] == ["orders", "users"]
    assert kept[0].confidence == 0.9  # untouched: all evidence survived
    assert report.milestone_count == 1


def test_escaping_or_absolute_paths_are_ungrounded(tmp_path):
    root = _repo(tmp_path)
    cm = _candidate(
        "escape",
        [
            Evidence(source="code", path="../outside.py", reason="escape"),
            Evidence(source="code", path="/etc/passwd", reason="absolute"),
            Evidence(source="code", path="src/auth/signup.py", reason="real"),
        ],
    )
    kept, report = ground_candidates([cm], repo_root=root)
    assert len(kept) == 1
    assert [ev.path for ev in kept[0].evidence] == ["src/auth/signup.py"]
    assert report.evidence_count == 2


def test_no_sources_means_no_change(tmp_path):
    cm = _candidate(
        "legacy",
        [
            Evidence(source="code", path="src/never/checked.py", reason="unchecked"),
            Evidence(source="db", table="unchecked", reason="unchecked"),
        ],
    )
    kept, report = ground_candidates([cm])
    assert kept == [cm]
    assert report.evidence_count == 0
    assert report.milestone_count == 0
