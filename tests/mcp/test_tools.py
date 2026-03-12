"""Tests for MCP tools."""

from pathlib import Path

import pytest

from skene.mcp.cache import AnalysisCache
from skene.mcp.tools import (
    get_codebase_overview,
    search_codebase,
)


class TestGetCodebaseOverview:
    """Tests for get_codebase_overview tool."""

    @pytest.mark.asyncio
    async def test_returns_overview_data(self, sample_repo_path: Path):
        """Should return overview with tree, file counts, and config files."""
        result = await get_codebase_overview(str(sample_repo_path))

        assert "path" in result
        assert "tree" in result
        assert "file_counts" in result
        assert "total_files" in result
        assert "config_files" in result

    @pytest.mark.asyncio
    async def test_tree_is_string(self, sample_repo_path: Path):
        """Tree should be a string representation."""
        result = await get_codebase_overview(str(sample_repo_path))

        assert isinstance(result["tree"], str)
        assert len(result["tree"]) > 0

    @pytest.mark.asyncio
    async def test_file_counts_by_extension(self, sample_repo_path: Path):
        """Should count files by extension."""
        result = await get_codebase_overview(str(sample_repo_path))

        file_counts = result["file_counts"]
        assert isinstance(file_counts, dict)
        # Sample repo has .py and .md files
        assert ".py" in file_counts or ".md" in file_counts

    @pytest.mark.asyncio
    async def test_total_files_matches_counts(self, sample_repo_path: Path):
        """Total files should match sum of counts."""
        result = await get_codebase_overview(str(sample_repo_path))

        total = sum(result["file_counts"].values())
        assert result["total_files"] == total

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_path(self):
        """Should raise for non-existent path."""
        with pytest.raises(ValueError, match="does not exist"):
            await get_codebase_overview("/nonexistent/path")

    @pytest.mark.asyncio
    async def test_raises_for_file_path(self, sample_repo_path: Path):
        """Should raise when path is a file, not directory."""
        file_path = sample_repo_path / "README.md"
        with pytest.raises(ValueError, match="not a directory"):
            await get_codebase_overview(str(file_path))


class TestSearchCodebase:
    """Tests for search_codebase tool."""

    @pytest.mark.asyncio
    async def test_finds_files_by_pattern(self, sample_repo_path: Path):
        """Should find files matching glob pattern."""
        result = await search_codebase(
            path=str(sample_repo_path),
            pattern="**/*.py",
        )

        assert "matches" in result
        assert "count" in result
        assert result["count"] > 0

        names = [m["name"] for m in result["matches"]]
        assert "main.py" in names or "utils.py" in names

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_matches(self, sample_repo_path: Path):
        """Should return empty list for no matches."""
        result = await search_codebase(
            path=str(sample_repo_path),
            pattern="**/*.nonexistent",
        )

        assert result["matches"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_respects_directory_parameter(self, sample_repo_path: Path):
        """Should search within specified directory."""
        result = await search_codebase(
            path=str(sample_repo_path),
            pattern="*.py",
            directory="src",
        )

        assert result["directory"] == "src"
        # All matches should be in src directory
        for match in result["matches"]:
            assert match["path"].startswith("src")

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_path(self):
        """Should raise for non-existent path."""
        with pytest.raises(ValueError, match="does not exist"):
            await search_codebase(
                path="/nonexistent/path",
                pattern="**/*.py",
            )


class TestCachePhaseOperations:
    """Tests for phase-specific cache operations."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> AnalysisCache:
        """Create a cache instance for testing."""
        return AnalysisCache(cache_dir=tmp_path / "cache")

    @pytest.mark.asyncio
    async def test_set_and_get_phase(self, cache: AnalysisCache, sample_repo_path: Path):
        """Should set and get phase data."""
        test_data = {"framework": "Next.js", "language": "TypeScript"}

        await cache.set_phase(sample_repo_path, "tech_stack", test_data)
        result = await cache.get_phase(sample_repo_path, "tech_stack")

        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_phase_returns_none_for_missing(self, cache: AnalysisCache, sample_repo_path: Path):
        """Should return None for missing phase data."""
        result = await cache.get_phase(sample_repo_path, "tech_stack")
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_phase(self, cache: AnalysisCache, sample_repo_path: Path):
        """Should clear specific phase data."""
        test_data = {"framework": "Next.js"}
        await cache.set_phase(sample_repo_path, "tech_stack", test_data)

        cleared = await cache.clear_phase(sample_repo_path, "tech_stack")
        assert cleared is True

        result = await cache.get_phase(sample_repo_path, "tech_stack")
        assert result is None

    @pytest.mark.asyncio
    async def test_phases_are_independent(self, cache: AnalysisCache, sample_repo_path: Path):
        """Different phases should be cached independently."""
        tech_stack = {"framework": "Next.js"}
        product_overview = {"overview": "A test product"}

        await cache.set_phase(sample_repo_path, "tech_stack", tech_stack)
        await cache.set_phase(sample_repo_path, "product_overview", product_overview)

        assert await cache.get_phase(sample_repo_path, "tech_stack") == tech_stack
        assert await cache.get_phase(sample_repo_path, "product_overview") == product_overview

        # Clearing one shouldn't affect the other
        await cache.clear_phase(sample_repo_path, "tech_stack")
        assert await cache.get_phase(sample_repo_path, "tech_stack") is None
        assert await cache.get_phase(sample_repo_path, "product_overview") == product_overview

    def test_invalid_phase_raises(self, cache: AnalysisCache, sample_repo_path: Path):
        """Should raise for invalid phase name."""
        with pytest.raises(ValueError, match="Unknown phase"):
            cache._compute_phase_cache_key(sample_repo_path, "invalid_phase")
