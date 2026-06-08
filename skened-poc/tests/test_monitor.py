from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from skened.models import JobStatus
from skened.service import DaemonService


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _enabled(settings, **extra):
    return settings.model_copy(update={"monitor_enabled": True, **extra})


def test_monitor_triggers_analysis_on_branch_switch(git_repo: Path, settings):
    async def run():
        svc = DaemonService(_enabled(settings))
        await svc.start()
        try:
            project = await svc.add_project(str(git_repo))  # checked out on 'main'; analyzes main
            await svc.queue.join()

            await svc.monitor._tick()  # records 'main'; already up to date → no new run
            await svc.queue.join()
            assert {r.branch for r in svc.list_runs(project.id)} == {"main"}

            _git(git_repo, "checkout", "feature")
            await svc.monitor._tick()  # detects the switch → enqueues 'feature'
            await svc.queue.join()
            runs = svc.list_runs(project.id)
            assert any(r.branch == "feature" and r.status == JobStatus.succeeded for r in runs)
        finally:
            await svc.stop()

    asyncio.run(run())


def test_monitor_triggers_on_new_commit(git_repo: Path, settings):
    async def run():
        svc = DaemonService(_enabled(settings))
        await svc.start()
        try:
            project = await svc.add_project(str(git_repo))
            await svc.queue.join()
            await svc.monitor._tick()  # records main@HEAD
            await svc.queue.join()

            (git_repo / "feature_flag.py").write_text("# new\n")
            _git(git_repo, "add", ".")
            _git(git_repo, "commit", "-m", "more")

            await svc.monitor._tick()  # commit changed HEAD → re-analyze main
            await svc.queue.join()
            main_runs = [r for r in svc.list_runs(project.id) if r.branch == "main"]
            assert len(main_runs) >= 2
        finally:
            await svc.stop()

    asyncio.run(run())


def test_monitor_switch_only_ignores_commits(git_repo: Path, settings):
    async def run():
        svc = DaemonService(_enabled(settings, monitor_on_commit=False))
        await svc.start()
        try:
            project = await svc.add_project(str(git_repo))
            await svc.queue.join()
            await svc.monitor._tick()  # record main
            await svc.queue.join()
            n0 = len(svc.list_runs(project.id))

            # Commit on the same branch → ignored when monitor_on_commit is off.
            (git_repo / "x.py").write_text("1\n")
            _git(git_repo, "add", ".")
            _git(git_repo, "commit", "-m", "c")
            await svc.monitor._tick()
            await svc.queue.join()
            assert len(svc.list_runs(project.id)) == n0

            # Switching branches still triggers analysis.
            _git(git_repo, "checkout", "feature")
            await svc.monitor._tick()
            await svc.queue.join()
            assert any(r.branch == "feature" for r in svc.list_runs(project.id))
        finally:
            await svc.stop()

    asyncio.run(run())


def test_monitor_disabled_does_not_analyze(git_repo: Path, settings):
    async def run():
        svc = DaemonService(settings.model_copy(update={"monitor_enabled": False}))
        await svc.start()
        try:
            project = await svc.add_project(str(git_repo))
            await svc.queue.join()
            n0 = len(svc.list_runs(project.id))
            _git(git_repo, "checkout", "feature")
            await svc.monitor._tick()  # disabled → no-op
            await svc.queue.join()
            assert len(svc.list_runs(project.id)) == n0
        finally:
            await svc.stop()

    asyncio.run(run())
