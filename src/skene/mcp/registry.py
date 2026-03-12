"""Tool registry and runner for MCP and chat integrations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skene.mcp.cache import AnalysisCache

# Import tools directly as submodule to avoid triggering mcp/__init__.py imports
from skene.mcp.tools import (
    analyze_features,
    analyze_growth_hubs,
    analyze_industry,
    analyze_product_overview,
    analyze_tech_stack,
    clear_cache,
    generate_growth_template_tool,
    generate_manifest,
    get_codebase_overview,
    get_manifest,
    search_codebase,
    write_analysis_outputs,
)


@dataclass(frozen=True)
class ToolDefinition:
    """Definition for a tool exposed to chat or MCP clients."""

    name: str
    description: str
    input_schema: dict[str, Any]


def get_cache_dir() -> Path:
    """Get cache directory from environment or default."""
    cache_dir = os.environ.get("SKENE_CACHE_DIR")
    if cache_dir:
        return Path(cache_dir)
    return Path.home() / ".cache" / "skene-mcp"


def get_cache_ttl() -> int:
    """Get cache TTL from environment or default."""
    try:
        return int(os.environ.get("SKENE_CACHE_TTL", "3600"))
    except ValueError:
        return 3600


def is_cache_enabled() -> bool:
    """Check if caching is enabled."""
    value = os.environ.get("SKENE_CACHE_ENABLED", "true")
    return value.lower() in ("true", "1", "yes")


def get_tool_definitions() -> list[ToolDefinition]:
    """Return the canonical list of tool definitions."""
    return [
        # =============================================================
        # Tier 1: Quick Tools
        # =============================================================
        ToolDefinition(
            name="get_codebase_overview",
            description=(
                "Get a quick overview of a codebase structure (<1s). "
                "Returns directory tree, file counts by extension, and detected config files. "
                "Use this first to understand the project structure before deeper analysis."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                },
                "required": ["path"],
            },
        ),
        ToolDefinition(
            name="search_codebase",
            description=(
                "Search for files matching a glob pattern (<1s). "
                "Use patterns like '**/*.py' for Python files or 'src/**/*.ts' for TypeScript in src."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g., '**/*.py', 'src/**/*.ts')",
                    },
                    "directory": {
                        "type": "string",
                        "description": "Subdirectory to search in (default: '.')",
                        "default": ".",
                    },
                },
                "required": ["path", "pattern"],
            },
        ),
        # =============================================================
        # Tier 2: Analysis Phase Tools (uses LLM)
        # =============================================================
        ToolDefinition(
            name="analyze_tech_stack",
            description=(
                "Analyze the technology stack of a codebase (5-15s). "
                "Detects framework, language, database, authentication, and deployment. "
                "Results are cached independently."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Skip cache and force re-analysis",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        ),
        ToolDefinition(
            name="analyze_product_overview",
            description=(
                "Extract product overview from README and documentation (5-15s). "
                "Returns product name, tagline, description, value proposition. "
                "Results are cached independently."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Skip cache and force re-analysis",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        ),
        ToolDefinition(
            name="analyze_growth_hubs",
            description=(
                "Identify growth hubs (viral/growth features) in the codebase (5-15s). "
                "Finds features like invitations, sharing, referrals, payments. "
                "Results are cached independently."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Skip cache and force re-analysis",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        ),
        ToolDefinition(
            name="analyze_features",
            description=(
                "Document user-facing features from the codebase (5-15s). "
                "Extracts feature information from source files. "
                "Results are cached independently."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Skip cache and force re-analysis",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        ),
        ToolDefinition(
            name="analyze_industry",
            description=(
                "Classify the industry/market vertical of a codebase (5-15s). "
                "Analyzes README and documentation to determine the product's industry, "
                "sub-verticals, and business model tags. "
                "Results are cached independently."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Skip cache and force re-analysis",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        ),
        # =============================================================
        # Tier 3: Generation Tools
        # =============================================================
        ToolDefinition(
            name="generate_manifest",
            description=(
                "Generate a GrowthManifest from cached analysis results (5-15s). "
                "IMPORTANT: Call analyze_tech_stack and analyze_growth_hubs FIRST to populate the cache. "
                "For product_docs=true, also call analyze_product_overview and analyze_features first. "
                "This tool combines the cached phase results into the final manifest."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                    "product_docs": {
                        "type": "boolean",
                        "description": "Generate DocsManifest v2.0 with product documentation",
                        "default": False,
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Skip cache and force re-analysis",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        ),
        ToolDefinition(
            name="generate_growth_template",
            description=(
                "Generate a PLG growth template from a manifest (5-15s). "
                "Creates a custom template with lifecycle stages, milestones, and metrics. "
                "Results are cached independently."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                    "business_type": {
                        "type": "string",
                        "description": (
                            "Business type hint (e.g., 'b2b-saas', 'marketplace'). LLM will infer if not provided."
                        ),
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Skip cache and force re-generation",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        ),
        ToolDefinition(
            name="write_analysis_outputs",
            description=(
                "Write analysis outputs to disk (<1s). "
                "Writes growth-manifest.json, and optionally "
                "product-docs.md, growth-template.json. "
                "IMPORTANT: Run generate_manifest and generate_growth_template FIRST "
                "to populate the cache before calling this tool."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                    "product_docs": {
                        "type": "boolean",
                        "description": "Generate product-docs.md",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        ),
        # =============================================================
        # Utility Tools
        # =============================================================
        ToolDefinition(
            name="get_manifest",
            description=(
                "Retrieve an existing growth manifest from disk without re-analyzing. "
                "Use this when you just need to read a previously generated manifest."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the repository",
                    },
                },
                "required": ["path"],
            },
        ),
        ToolDefinition(
            name="clear_cache",
            description=(
                "Clear cached analysis results. Useful when you want to force "
                "fresh analysis or troubleshoot caching issues."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to clear cache for. If not provided, clears all cache.",
                    },
                },
            },
        ),
    ]


class NoOpCache:
    """No-op cache for when caching is disabled."""

    async def get(self, *args, **kwargs):
        return None

    async def set(self, *args, **kwargs):
        pass

    async def get_phase(self, *args, **kwargs):
        return None

    async def set_phase(self, *args, **kwargs):
        pass

    async def clear(self, *args, **kwargs):
        return 0


class ToolRunner:
    """Execute tools with cache handling."""

    def __init__(self, cache: AnalysisCache, cache_enabled: bool = True) -> None:
        self.cache = cache
        self.cache_enabled = cache_enabled

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool call by name."""
        cache = self.cache if self.cache_enabled else NoOpCache()

        # Tier 1: Quick Tools
        if name == "get_codebase_overview":
            return await get_codebase_overview(path=arguments["path"])

        if name == "search_codebase":
            return await search_codebase(
                path=arguments["path"],
                pattern=arguments["pattern"],
                directory=arguments.get("directory", "."),
            )

        # Tier 2: Analysis Phase Tools
        if name == "analyze_tech_stack":
            return await analyze_tech_stack(
                path=arguments["path"],
                cache=cache,
                force_refresh=arguments.get("force_refresh", False),
            )

        if name == "analyze_product_overview":
            return await analyze_product_overview(
                path=arguments["path"],
                cache=cache,
                force_refresh=arguments.get("force_refresh", False),
            )

        if name == "analyze_growth_hubs":
            return await analyze_growth_hubs(
                path=arguments["path"],
                cache=cache,
                force_refresh=arguments.get("force_refresh", False),
            )

        if name == "analyze_features":
            return await analyze_features(
                path=arguments["path"],
                cache=cache,
                force_refresh=arguments.get("force_refresh", False),
            )

        if name == "analyze_industry":
            return await analyze_industry(
                path=arguments["path"],
                cache=cache,
                force_refresh=arguments.get("force_refresh", False),
            )

        # Tier 3: Generation Tools
        if name == "generate_manifest":
            return await generate_manifest(
                path=arguments["path"],
                cache=cache,
                auto_analyze=False,  # Require phase tools to be called first
                product_docs=arguments.get("product_docs", False),
                force_refresh=arguments.get("force_refresh", False),
            )

        if name == "generate_growth_template":
            return await generate_growth_template_tool(
                path=arguments["path"],
                cache=cache,
                business_type=arguments.get("business_type"),
                force_refresh=arguments.get("force_refresh", False),
            )

        if name == "write_analysis_outputs":
            return await write_analysis_outputs(
                path=arguments["path"],
                cache=cache,
                product_docs=arguments.get("product_docs", False),
            )

        # Utility Tools
        if name == "get_manifest":
            return await get_manifest(path=arguments["path"])

        if name == "clear_cache":
            return await clear_cache(
                cache=self.cache,
                path=arguments.get("path"),
            )

        raise ValueError(f"Unknown tool: {name}")
