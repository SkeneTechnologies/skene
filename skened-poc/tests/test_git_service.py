from __future__ import annotations

import asyncio
from pathlib import Path

from skened import git_service as git


def test_list_branches_and_default(git_repo: Path):
    async def run():
        assert await git.is_git_repo(git_repo)
        branches = {b.name: b for b in await git.list_branches(git_repo)}
        assert set(branches) == {"main", "feature"}
        assert branches["main"].committed_at is not None  # last-commit date populated
        assert await git.default_branch(git_repo) == "main"
        assert await git.current_branch(git_repo) == "main"
        # feature has its own HEAD commit, distinct from main
        assert await git.head_commit(git_repo, "feature") != await git.head_commit(git_repo, "main")

    asyncio.run(run())


def test_worktree_roundtrip_does_not_touch_checkout(git_repo: Path, tmp_path: Path):
    async def run():
        feature_commit = await git.head_commit(git_repo, "feature")
        dest = Path(tmp_path) / "wt" / feature_commit
        await git.add_worktree(git_repo, feature_commit, dest)
        try:
            # Worktree contains the feature branch's file...
            assert (dest / "feature.txt").exists()
            # ...while the user's checkout stays on main, untouched.
            assert await git.current_branch(git_repo) == "main"
            assert not (git_repo / "feature.txt").exists()
        finally:
            await git.remove_worktree(git_repo, dest)
        assert not dest.exists()

    asyncio.run(run())
