"""Shared pytest fixtures for skene tests."""

from pathlib import Path
from typing import Any

import psycopg
import pytest

from skene.codebase import CodebaseExplorer


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --db-url option for live PostgreSQL integration tests."""
    parser.addoption(
        "--db-url",
        action="store",
        default=None,
        help="PostgreSQL connection string for live database tests (e.g. postgresql://user:pass@localhost/db). "
        "Tests marked with @pytest.mark.db are skipped when not provided.",
    )


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


@pytest.fixture
def pg_conn(request: pytest.FixtureRequest) -> psycopg.Connection[Any] | None:
    """Return a live psycopg connection when --db-url is provided, else None.

    The connection object carries a ``._db_url`` attribute so tests can pass
    the original URL back into :func:`introspect_db`::

        def test_something(self, pg_conn):
            pytest.skip("no --db-url") if pg_conn is None else None
            index = introspect_db(pg_conn._db_url)
            # ... use pg_conn for setup/teardown ...
    """
    db_url = request.config.getoption("--db-url", default=None)
    if db_url is None:
        return None
    conn = psycopg.connect(db_url)
    conn._db_url = db_url  # type: ignore[attr-defined]
    return conn
