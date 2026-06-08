"""Git operations via subprocess.

Subprocess (not a library) is used deliberately: ``git worktree`` support is most
reliable through the real CLI, and worktrees are how we analyze a branch without ever
disturbing the user's active checkout.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import NamedTuple


class GitError(RuntimeError):
    pass


class GitBranch(NamedTuple):
    name: str
    commit: str
    committed_at: int | None  # last-commit committer date, unix seconds


async def _git(repo: Path, *args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", str(repo), *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {err.decode().strip() or out.decode().strip()}")
    return out.decode()


async def is_git_repo(path: Path) -> bool:
    try:
        out = await _git(path, "rev-parse", "--is-inside-work-tree")
    except GitError:
        return False
    return out.strip() == "true"


async def repo_toplevel(path: Path) -> Path:
    out = await _git(path, "rev-parse", "--show-toplevel")
    return Path(out.strip())


async def current_branch(repo: Path) -> str | None:
    """Branch name, or None when in detached-HEAD state."""
    out = (await _git(repo, "rev-parse", "--abbrev-ref", "HEAD")).strip()
    return None if out == "HEAD" else out


async def head_commit(repo: Path, ref: str = "HEAD") -> str:
    return (await _git(repo, "rev-parse", ref)).strip()


async def default_branch(repo: Path) -> str:
    """Best-effort default branch: origin/HEAD target, else main/master, else current."""
    try:
        out = (await _git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")).strip()
        if out:
            return out.rsplit("/", 1)[-1]
    except GitError:
        pass
    branches = {b.name for b in await list_branches(repo)}
    for candidate in ("main", "master"):
        if candidate in branches:
            return candidate
    cur = await current_branch(repo)
    if cur:
        return cur
    return next(iter(sorted(branches)), "main")


async def list_branches(repo: Path) -> list[GitBranch]:
    """Local branches with head commit and last-commit date."""
    out = await _git(
        repo,
        "for-each-ref",
        "--format=%(refname:short)%09%(objectname)%09%(committerdate:unix)",
        "refs/heads",
    )
    result: list[GitBranch] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        name = parts[0]
        commit = parts[1] if len(parts) > 1 else ""
        ts: int | None = None
        if len(parts) > 2 and parts[2].strip():
            try:
                ts = int(parts[2])
            except ValueError:
                ts = None
        result.append(GitBranch(name, commit, ts))
    return result


async def diff_name_status(repo: Path, base: str, target: str) -> list[list[str]]:
    """Tab-split ``git diff --name-status -M`` rows between two refs/commits.

    Each row is like ``["M", "path"]``, ``["A", "path"]``, ``["D", "path"]`` or
    ``["R100", "old", "new"]`` for renames.
    """
    out = await _git(repo, "diff", "--name-status", "-M", base, target)
    rows: list[list[str]] = []
    for line in out.splitlines():
        if line.strip():
            rows.append(line.split("\t"))
    return rows


async def diff(repo: Path, base: str, target: str, max_chars: int = 20_000) -> str:
    """Unified diff between two refs/commits, truncated for LLM context budgets."""
    out = await _git(repo, "diff", base, target)
    if len(out) > max_chars:
        return out[:max_chars] + "\n... [diff truncated]"
    return out


async def remote_url(repo: Path, remote: str = "origin") -> str | None:
    try:
        return (await _git(repo, "remote", "get-url", remote)).strip() or None
    except GitError:
        return None


# --- worktrees -----------------------------------------------------------------
async def add_worktree(repo: Path, commit: str, dest: Path) -> Path:
    """Create a detached worktree at ``commit`` under ``dest``. Idempotent-ish: an
    existing dir is removed first so re-runs at the same commit are clean."""
    if dest.exists():
        await remove_worktree(repo, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    await _git(repo, "worktree", "add", "--detach", "--force", str(dest), commit)
    return dest


async def remove_worktree(repo: Path, dest: Path) -> None:
    try:
        await _git(repo, "worktree", "remove", "--force", str(dest))
    except GitError:
        # Fall back to pruning stale administrative entries if the dir is already gone.
        await _git(repo, "worktree", "prune")


# --- remote sync (used by a future "pull from GitHub" feature) ------------------
async def fetch(repo: Path, remote: str = "origin") -> str:
    return await _git(repo, "fetch", remote)


async def pull(repo: Path, branch: str, remote: str = "origin") -> str:
    return await _git(repo, "pull", remote, branch)
