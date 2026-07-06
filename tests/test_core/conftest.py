"""Fixtures for core-service tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from skene.core.services import CoreServices, create_services


@pytest.fixture
async def services(tmp_path: Path) -> CoreServices:
    def _no_llm():
        raise AssertionError("test did not configure an LLM client")

    built = await create_services(tmp_path / "skene.db", llm_factory=_no_llm)
    yield built
    await built.close()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    directory = tmp_path / "workspace"
    directory.mkdir()
    return directory
