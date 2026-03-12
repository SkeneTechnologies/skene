"""Shared pytest fixtures for skene tests."""

from pathlib import Path

import pytest

from skene.codebase import CodebaseExplorer


@pytest.fixture
def fixtures_path() -> Path:
    """Path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_repo_path(fixtures_path: Path) -> Path:
    """Path to the sample repository fixture."""
    return fixtures_path / "sample_repo"


@pytest.fixture
def codebase_explorer(sample_repo_path: Path) -> CodebaseExplorer:
    """CodebaseExplorer instance for the sample repository."""
    return CodebaseExplorer(sample_repo_path)
