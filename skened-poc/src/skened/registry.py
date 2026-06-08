"""Project registry: validate, persist, and remove git projects."""

from __future__ import annotations

import uuid
from pathlib import Path

from . import git_service as git
from .db import Database
from .models import Project


class RegistryError(RuntimeError):
    pass


class ProjectRegistry:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def add_project(self, path: str | Path, name: str | None = None) -> Project:
        repo = Path(path).expanduser().resolve()
        if not repo.exists():
            raise RegistryError(f"path does not exist: {repo}")
        if not await git.is_git_repo(repo):
            raise RegistryError(f"not a git repository: {repo}")

        # Normalize to the repo root so worktree commands always run from the top level.
        repo = await git.repo_toplevel(repo)
        default = await git.default_branch(repo)
        remote = await git.remote_url(repo)

        project = Project(
            id=uuid.uuid4().hex[:12],
            name=name or repo.name,
            path=str(repo),
            default_branch=default,
            github_remote=remote,
        )
        self._db.insert_project(project)
        return project

    def get_project(self, project_id: str) -> Project | None:
        return self._db.get_project(project_id)

    def list_projects(self) -> list[Project]:
        return self._db.list_projects()

    def remove_project(self, project_id: str) -> bool:
        return self._db.delete_project(project_id)
