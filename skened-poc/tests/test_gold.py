from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from skened.service import DaemonService, NotFoundError


def test_gold_service_crud(git_repo: Path, settings):
    async def run():
        svc = DaemonService(settings)
        await svc.start()
        try:
            project = await svc.registry.add_project(git_repo)

            # No gold yet.
            assert svc.has_gold(project.id) is False
            with pytest.raises(NotFoundError):
                svc.get_gold(project.id)

            # Build automatically from the default branch.
            gold = await svc.create_gold_from_branch(project.id)
            assert svc.has_gold(project.id) is True
            assert svc.get_gold(project.id).product.name == gold.product.name

            # Manually edit (full replacement) and read back.
            edited = gold.model_copy(deep=True)
            edited.product.description = "hand-edited gold standard"
            svc.set_gold(project.id, edited)
            assert svc.get_gold(project.id).product.description == "hand-edited gold standard"

            # Delete.
            assert svc.delete_gold(project.id) is True
            assert svc.has_gold(project.id) is False
            assert svc.delete_gold(project.id) is False
        finally:
            await svc.stop()

    asyncio.run(run())


def test_gold_from_branch_reuses_existing_run(git_repo: Path, settings):
    """If the branch HEAD was already analyzed, the gold build reuses that journey
    rather than re-running analysis."""
    async def run():
        svc = DaemonService(settings)
        await svc.start()
        try:
            project = await svc.add_project(str(git_repo))  # auto-enqueues main
            await svc.queue.join()
            existing = await svc.get_branch_journey(project.id, "main")
            gold = await svc.create_gold_from_branch(project.id, "main")
            assert gold.product.source_commit == existing.product.source_commit
        finally:
            await svc.stop()

    asyncio.run(run())
