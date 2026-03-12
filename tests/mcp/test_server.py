"""Tests for MCP server tool definitions and handlers."""

from pathlib import Path

import pytest

from skene.mcp.cache import AnalysisCache
from skene.mcp.tools import (
    clear_cache,
    get_codebase_overview,
    get_manifest,
    search_codebase,
)


class TestServerToolDefinitions:
    """Tests for expected tool structure based on our implementation."""

    def test_all_expected_tools_exist(self):
        """Verify all expected tools are importable from tools module."""
        from skene.mcp import tools

        # Tier 1: Quick Tools
        assert hasattr(tools, "get_codebase_overview")
        assert hasattr(tools, "search_codebase")

        # Tier 2: Analysis Phase Tools
        assert hasattr(tools, "analyze_tech_stack")
        assert hasattr(tools, "analyze_product_overview")
        assert hasattr(tools, "analyze_growth_hubs")
        assert hasattr(tools, "analyze_features")

        # Tier 3: Generation Tools
        assert hasattr(tools, "generate_manifest")
        assert hasattr(tools, "generate_growth_template_tool")
        assert hasattr(tools, "write_analysis_outputs")

        # Utility Tools
        assert hasattr(tools, "get_manifest")
        assert hasattr(tools, "clear_cache")


class TestToolHandlers:
    """Tests for tool call handlers via direct function calls."""

    @pytest.mark.asyncio
    async def test_get_codebase_overview_handler(self, sample_repo_path: Path):
        """Should handle get_codebase_overview calls."""
        result = await get_codebase_overview(str(sample_repo_path))

        assert "tree" in result
        assert "file_counts" in result
        assert "path" in result

    @pytest.mark.asyncio
    async def test_search_codebase_handler(self, sample_repo_path: Path):
        """Should handle search_codebase calls."""
        result = await search_codebase(
            path=str(sample_repo_path),
            pattern="**/*.py",
        )

        assert "matches" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_invalid_path_returns_error(self):
        """Should raise error for invalid paths."""
        with pytest.raises(ValueError, match="does not exist"):
            await get_codebase_overview("/nonexistent/path")

    @pytest.mark.asyncio
    async def test_get_manifest_handler(self, sample_repo_path: Path):
        """Should handle get_manifest calls."""
        result = await get_manifest(str(sample_repo_path))

        # No manifest exists in sample repo, so should indicate not found
        assert result.get("exists") is False

    @pytest.mark.asyncio
    async def test_clear_cache_handler(self, tmp_path: Path):
        """Should handle clear_cache calls."""
        cache = AnalysisCache(cache_dir=tmp_path / "cache")
        result = await clear_cache(cache=cache)

        assert "cleared" in result
        assert "message" in result
