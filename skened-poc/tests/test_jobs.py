from __future__ import annotations

import asyncio
from pathlib import Path

from skened.models import JobStatus
from skened.service import DaemonService


def test_enqueue_runs_and_persists_journey(git_repo: Path, settings):
    async def run():
        svc = DaemonService(settings)
        await svc.start()
        try:
            project = await svc.registry.add_project(git_repo)
            runs = await svc.enqueue_analysis(project.id, branch="main")
            assert len(runs) == 1
            await svc.queue.join()

            run = svc.get_run(runs[0].id)
            assert run.status == JobStatus.succeeded
            assert run.journey_path is not None
            assert Path(run.journey_path).exists()

            journey = await svc.get_branch_journey(project.id, "main")
            assert journey.product.source_commit == run.commit

            # Worktree was cleaned up after the run (no leftovers for this project).
            wt_dir = settings.worktrees_dir / project.id
            assert not wt_dir.exists() or not any(wt_dir.iterdir())

            # Idempotent: re-enqueueing the same up-to-date commit does nothing.
            again = await svc.enqueue_analysis(project.id, branch="main")
            assert again == []
        finally:
            await svc.stop()

    asyncio.run(run())


def test_analyze_all_branches(git_repo: Path, settings):
    async def run():
        svc = DaemonService(settings)
        await svc.start()
        try:
            project = await svc.registry.add_project(git_repo)
            runs = await svc.enqueue_analysis(project.id, all_branches=True)
            assert {r.branch for r in runs} == {"main", "feature"}
            await svc.queue.join()
            branches = {b.name: b for b in await svc.list_branches(project.id)}
            assert branches["main"].up_to_date
            assert branches["feature"].up_to_date
            assert branches["main"].is_default
            assert not branches["feature"].is_default
        finally:
            await svc.stop()

    asyncio.run(run())
