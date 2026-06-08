from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from skened.api import create_app
from skened.comparison import DeltaStatus, compare_journeys
from skened.journey import Evidence, EvidenceSource, Journey, Milestone, Product, Stage


def _ev(path: str) -> Evidence:
    return Evidence(source=EvidenceSource.code, path=path, reason="r")


def _journey(stages: list[Stage]) -> Journey:
    return Journey(
        product=Product(name="p", generated_at=datetime.now(timezone.utc)),
        stages=stages,
    )


def test_compare_classifies_matched_changed_missing_added():
    target = _journey([
        Stage(id="discovery", order=1, name="Discovery", milestones=[
            Milestone(id="signup", order=1, name="Signup", description="d", evidence=[_ev("a.py")])]),
        Stage(id="expansion", order=6, name="Expansion", milestones=[
            Milestone(id="billing", order=1, name="Billing", description="d", evidence=[_ev("b.py")])]),
    ])
    candidate = _journey([
        Stage(id="discovery", order=1, name="Discovery", milestones=[
            Milestone(id="signup", order=1, name="Signup", description="d", evidence=[_ev("a.py"), _ev("c.py")])]),
        Stage(id="virality", order=7, name="Virality", milestones=[
            Milestone(id="referral", order=1, name="Referral", description="d", evidence=[_ev("r.py")])]),
    ])

    rep = compare_journeys(target, candidate, kind="gap", target_label="gold", candidate_label="feat")

    by_id = {d.id: d for d in rep.deltas}
    assert by_id["signup"].status == DeltaStatus.changed
    assert any("c.py" in c for c in by_id["signup"].changes)
    assert by_id["billing"].status == DeltaStatus.missing
    assert by_id["referral"].status == DeltaStatus.added

    assert (rep.matched, rep.changed, rep.missing, rep.added) == (0, 1, 1, 1)
    assert rep.coverage == 0.5  # (matched + changed) / 2 target milestones


def test_detects_stage_move():
    target = _journey([Stage(id="onboarding", order=2, name="Onboarding", milestones=[
        Milestone(id="api_key", order=1, name="API key", description="d", evidence=[_ev("k.py")])])])
    candidate = _journey([Stage(id="activation", order=3, name="Activation", milestones=[
        Milestone(id="api_key", order=1, name="API key", description="d", evidence=[_ev("k.py")])])])

    rep = compare_journeys(target, candidate, kind="drift", target_label="main", candidate_label="dev")
    d = rep.deltas[0]
    assert d.status == DeltaStatus.changed
    assert any("onboarding → activation" in c for c in d.changes)


# --- API integration: gap vs gold + drift between branches ---------------------
def _branch_repo(tmp_path: Path):
    import subprocess

    def g(*a):
        subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)

    repo = Path(tmp_path) / "proj"
    (repo / "app" / "signup").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    g("init", "-b", "main")
    g("config", "user.email", "t@e.com")
    g("config", "user.name", "T")
    (repo / "app" / "signup" / "route.ts").write_text("export async function POST(){/* signup */}\n")
    (repo / "src" / "billing.ts").write_text("import Stripe from 'stripe'; // subscription\n")
    g("add", ".")
    g("commit", "-m", "init")
    g("checkout", "-b", "feature")
    (repo / "src" / "referral.ts").write_text("// referral invite share-link\n")
    g("add", ".")
    g("commit", "-m", "referral")
    g("checkout", "main")
    return repo


def test_gap_and_drift_api(tmp_path, settings):
    repo = _branch_repo(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        project = client.post("/projects", json={"path": str(repo)}).json()
        pid = project["id"]
        # analyze both branches
        client.post(f"/projects/{pid}/analyze", json={"all": True})
        # wait for runs
        import time
        for _ in range(80):
            runs = client.get(f"/projects/{pid}/runs").json()
            if runs and all(r["status"] in ("succeeded", "failed") for r in runs) and len(runs) >= 2:
                break
            time.sleep(0.05)

        # gap before a gold standard exists -> 404
        assert client.get(f"/projects/{pid}/branches/main/gap").status_code == 404

        # build gold from main, then gap(main) should be full coverage
        client.post(f"/projects/{pid}/gold/from-branch", json={})
        gap_main = client.get(f"/projects/{pid}/branches/main/gap").json()
        assert gap_main["coverage"] == 1.0
        assert gap_main["missing"] == 0

        # feature added a virality milestone -> drift(main, feature) shows it as "added"
        drift = client.get(f"/projects/{pid}/drift", params={"base": "main", "head": "feature"}).json()
        assert drift["added"] >= 1
        assert any(d["status"] == "added" and d["candidate_stage"] == "virality" for d in drift["deltas"])

        # drift against an unanalyzed branch -> 404
        assert client.get(f"/projects/{pid}/drift", params={"base": "main", "head": "nope"}).status_code == 404
