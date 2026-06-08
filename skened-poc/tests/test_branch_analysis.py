from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from skened.service import DaemonService


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def _build_repo(tmp_path: Path) -> Path:
    """main: a signup route + a billing file. Then two branches off main:
    - 'feature' adds a referral file (a real journey change → virality)
    - 'docs' only edits the README (no journey-relevant change)
    """
    repo = Path(tmp_path) / "proj"
    (repo / "app" / "signup").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    (repo / "README.md").write_text("# proj\n")
    (repo / "app" / "signup" / "route.ts").write_text("export async function POST(){/* signup */}\n")
    (repo / "src" / "billing.ts").write_text("import Stripe from 'stripe'; // subscription checkout\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    _git(repo, "checkout", "-b", "feature")
    (repo / "src" / "referral.ts").write_text("// referral invite share-link\nexport function invite(){}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add referral")

    _git(repo, "checkout", "main")
    _git(repo, "checkout", "-b", "docs")
    (repo / "README.md").write_text("# proj\n\nMore docs, no code.\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "docs only")

    _git(repo, "checkout", "main")
    return repo


def test_branch_is_branched_from_default_with_edits(tmp_path, settings):
    async def run():
        repo = _build_repo(tmp_path)
        svc = DaemonService(settings)
        await svc.start()
        try:
            project = await svc.add_project(str(repo))  # auto-analyzes main (the base)
            await svc.queue.join()
            base = await svc.get_branch_journey(project.id, "main")
            base_stages = {s.id for s in base.stages}
            # main built from scratch: signup → discovery, billing → expansion
            assert "discovery" in base_stages
            assert "expansion" in base_stages
            assert "virality" not in base_stages

            # Analyze the feature branch: should inherit base + add virality from referral.ts
            await svc.enqueue_analysis(project.id, branch="feature")
            await svc.queue.join()
            feature = await svc.get_branch_journey(project.id, "feature")
            feature_stages = {s.id for s in feature.stages}
            assert "virality" in feature_stages           # the branch's edit
            assert "discovery" in feature_stages          # inherited verbatim from base
            assert "expansion" in feature_stages          # inherited verbatim from base
            assert "branched from 'main'" in (feature.product.description or "").lower()

            # The inherited discovery milestones are identical to the base's.
            base_disc = {m.id for s in base.stages if s.id == "discovery" for m in s.milestones}
            feat_disc = {m.id for s in feature.stages if s.id == "discovery" for m in s.milestones}
            assert base_disc == feat_disc
        finally:
            await svc.stop()

    asyncio.run(run())


def test_list_branches_pins_current_then_default(git_repo, settings):
    async def run():
        svc = DaemonService(settings)
        await svc.start()
        try:
            _git(git_repo, "checkout", "feature")  # current = feature, default stays main
            project = await svc.add_project(str(git_repo))
            order = [b.name for b in await svc.list_branches(project.id)]
            assert order[0] == "feature"  # current pinned first
            assert order[1] == "main"     # default next
        finally:
            await svc.stop()

    asyncio.run(run())


def test_incremental_update_uses_branch_own_previous_journey(tmp_path, settings):
    async def run():
        repo = _build_repo(tmp_path)  # main(signup,billing); feature(+referral)
        svc = DaemonService(settings)
        await svc.start()
        try:
            project = await svc.add_project(str(repo))
            await svc.queue.join()

            # First feature analysis → branched from the default branch.
            await svc.enqueue_analysis(project.id, branch="feature")
            await svc.queue.join()
            feat1 = await svc.get_branch_journey(project.id, "feature")
            assert "branched from 'main'" in (feat1.product.description or "").lower()
            assert "virality" in {s.id for s in feat1.stages}

            # New commit on feature.
            _git(repo, "checkout", "feature")
            (repo / "src" / "email.ts").write_text("import sendgrid from '@sendgrid/mail';\n")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "add email")
            _git(repo, "checkout", "main")

            # Re-analysis is incremental from feature's OWN previous journey (not from main).
            await svc.enqueue_analysis(project.id, branch="feature")
            await svc.queue.join()
            feat2 = await svc.get_branch_journey(project.id, "feature")
            assert "branched from 'feature'" in (feat2.product.description or "").lower()
            # virality came from feature's own prior journey, carried through verbatim.
            assert "virality" in {s.id for s in feat2.stages}
        finally:
            await svc.stop()

    asyncio.run(run())


def test_default_branch_updates_incrementally(tmp_path, settings):
    async def run():
        repo = _build_repo(tmp_path)
        svc = DaemonService(settings)
        await svc.start()
        try:
            project = await svc.add_project(str(repo))  # main: first analysis = full pipeline
            await svc.queue.join()
            main1 = await svc.get_branch_journey(project.id, "main")
            assert "branched from" not in (main1.product.description or "").lower()

            # New commit on the default branch.
            (repo / "src" / "invite.ts").write_text("// referral invite share-link\n")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "main update")

            await svc.enqueue_analysis(project.id, branch="main")
            await svc.queue.join()
            main2 = await svc.get_branch_journey(project.id, "main")
            # default branch updates are now incremental from its own previous journey
            assert "branched from 'main'" in (main2.product.description or "").lower()
        finally:
            await svc.stop()

    asyncio.run(run())


def test_branch_with_no_code_change_equals_base(tmp_path, settings):
    async def run():
        repo = _build_repo(tmp_path)
        svc = DaemonService(settings)
        await svc.start()
        try:
            project = await svc.add_project(str(repo))
            await svc.queue.join()
            base = await svc.get_branch_journey(project.id, "main")

            await svc.enqueue_analysis(project.id, branch="docs")
            await svc.queue.join()
            docs = await svc.get_branch_journey(project.id, "docs")

            # README-only change → same stages and milestones as the base journey.
            assert {s.id for s in docs.stages} == {s.id for s in base.stages}
            base_ms = {(s.id, m.id) for s in base.stages for m in s.milestones}
            docs_ms = {(s.id, m.id) for s in docs.stages for m in s.milestones}
            assert docs_ms == base_ms
        finally:
            await svc.stop()

    asyncio.run(run())
