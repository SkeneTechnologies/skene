from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from skened.db import Database
from skened.registry import ProjectRegistry, RegistryError


def test_add_list_remove(git_repo: Path, settings):
    db = Database(settings.db_path)
    reg = ProjectRegistry(db)

    project = asyncio.run(reg.add_project(git_repo))
    assert project.default_branch == "main"
    assert project.path == str(git_repo)

    assert [p.id for p in reg.list_projects()] == [project.id]
    assert reg.get_project(project.id).name == git_repo.name

    assert reg.remove_project(project.id) is True
    assert reg.list_projects() == []
    db.close()


def test_rejects_non_git_path(tmp_path: Path, settings):
    db = Database(settings.db_path)
    reg = ProjectRegistry(db)
    not_a_repo = Path(tmp_path) / "plain"
    not_a_repo.mkdir()
    with pytest.raises(RegistryError):
        asyncio.run(reg.add_project(not_a_repo))
    db.close()
