"""Working-branch monitor.

Polls each registered project's *checked-out* HEAD; when the current ``(branch, commit)``
changes it enqueues analysis for that branch. Reuses ``DaemonService.enqueue_analysis``,
which is idempotent (it skips a branch already analyzed at its current commit), so ticks are
cheap and safe to repeat.

All knobs are read live from settings each tick, so the dashboard can toggle them without a
restart: ``monitor_enabled`` (off → idle), ``monitor_interval`` (poll cadence), and
``monitor_on_commit`` (when False, fire only on branch *switch*, not on new commits to the
current branch). Polling (not a filesystem watcher) keeps it dependency-free and robust.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from . import git_service as git

logger = logging.getLogger("skened.monitor")


class WorkingBranchMonitor:
    def __init__(self, service) -> None:
        self._svc = service
        self._task: asyncio.Task | None = None
        # project_id -> last observed (branch, commit) of the checked-out HEAD
        self._seen: dict[str, tuple[str, str]] = {}

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="skened-monitor")
        logger.info("working-branch monitor started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(max(0.5, self._svc.settings.monitor_interval))
            try:
                await self._tick()
            except Exception:  # noqa: BLE001 — a bad tick must never kill the monitor
                logger.exception("monitor tick failed")

    async def _tick(self) -> None:
        if not self._svc.settings.monitor_enabled:
            return
        on_commit = self._svc.settings.monitor_on_commit
        for project in self._svc.list_projects():
            state = await self._current(project)
            if state is None:  # detached HEAD or unreadable repo — ignore
                continue
            prev = self._seen.get(project.id)
            if prev == state:
                continue
            self._seen[project.id] = state
            branch, commit = state
            # Suppress commit-only changes on the same branch when on_commit is off.
            if prev is not None and prev[0] == branch and not on_commit:
                logger.debug("project %s: new commit on %s but monitor_on_commit=off — skipping",
                             project.id, branch)
                continue
            logger.info("project %s: checked-out %s@%s changed — triggering analysis",
                        project.id, branch, commit[:8])
            try:
                await self._svc.enqueue_analysis(project.id, branch=branch)
            except Exception:  # noqa: BLE001
                logger.exception("auto-analysis enqueue failed for project %s", project.id)

    async def _current(self, project) -> tuple[str, str] | None:
        repo = Path(project.path)
        try:
            branch = await git.current_branch(repo)
            if branch is None:
                return None
            commit = await git.head_commit(repo)
        except git.GitError:
            return None
        return branch, commit
