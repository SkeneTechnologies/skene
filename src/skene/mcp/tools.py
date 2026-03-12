"""MCP tools for skene analysis.

These tools reuse the same analysis logic as the CLI to ensure consistent behavior.
Tools are organized into tiers:
- Tier 1: Quick tools (no LLM) - get_codebase_overview, search_codebase
- Tier 2: Analysis phase tools - analyze_tech_stack, analyze_product_overview, etc.
- Tier 3: Generation tools - generate_manifest, generate_growth_template, write_analysis_outputs
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from skene.config import default_model_for_provider, load_config
from skene.mcp.cache import AnalysisCache


def _json_serializer(obj: Any) -> str:
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# =============================================================================
# Tier 1: Quick Tools (< 1s, no LLM)
# =============================================================================


async def get_codebase_overview(path: str) -> dict[str, Any]:
    """Get a quick overview of a codebase structure.

    This is a fast tool (<1s) that provides:
    - Directory tree structure
    - File counts by extension
    - Detected configuration files

    Args:
        path: Absolute path to the repository

    Returns:
        Overview data with tree, file_counts, and config_files
    """
    from skene.codebase import CodebaseExplorer

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    codebase = CodebaseExplorer(repo_path)

    # Get directory tree
    tree_result = await codebase.get_directory_tree(".", max_depth=3)
    tree = tree_result.get("tree", "")

    # Count files by extension
    file_counts: dict[str, int] = {}
    config_files: list[str] = []

    # Common config file patterns
    config_patterns = [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "Gemfile",
        "composer.json",
        "tsconfig.json",
        "docker-compose.yml",
        "Dockerfile",
        ".env.example",
        "vercel.json",
        "netlify.toml",
    ]

    # Search for all files and count by extension
    search_result = await codebase.search_files(".", "**/*")
    for match in search_result.get("matches", []):
        if match["type"] == "file":
            file_path = match["path"]
            file_name = match["name"]

            # Count by extension
            ext = Path(file_path).suffix.lower() or "(no extension)"
            file_counts[ext] = file_counts.get(ext, 0) + 1

            # Track config files
            if file_name in config_patterns:
                config_files.append(file_path)

    # Sort file counts by count descending
    sorted_counts = dict(sorted(file_counts.items(), key=lambda x: x[1], reverse=True))

    return {
        "path": str(repo_path),
        "tree": tree,
        "file_counts": sorted_counts,
        "total_files": sum(file_counts.values()),
        "config_files": sorted(config_files),
    }


async def search_codebase(
    path: str,
    pattern: str,
    directory: str = ".",
) -> dict[str, Any]:
    """Search for files matching a glob pattern.

    This is a fast tool (<1s) for finding files by pattern.

    Args:
        path: Absolute path to the repository
        pattern: Glob pattern (e.g., "**/*.py", "src/**/*.ts")
        directory: Subdirectory to search in (default: ".")

    Returns:
        Search results with matched files
    """
    from skene.codebase import CodebaseExplorer

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    codebase = CodebaseExplorer(repo_path)
    result = await codebase.search_files(directory, pattern)

    return {
        "path": str(repo_path),
        "pattern": pattern,
        "directory": directory,
        "matches": result.get("matches", []),
        "count": result.get("count", 0),
    }


# =============================================================================
# Tier 2: Analysis Phase Tools (5-15s each, uses LLM)
# =============================================================================


def _get_llm_client():
    """Create LLM client from config/environment."""
    from skene.llm import create_llm_client

    config = load_config()
    api_key = os.environ.get("SKENE_API_KEY") or config.api_key
    provider = os.environ.get("SKENE_PROVIDER") or config.provider
    model = os.environ.get("SKENE_MODEL") or config.get("model") or default_model_for_provider(provider)

    is_local_provider = provider.lower() in ("lmstudio", "lm-studio", "lm_studio", "ollama")

    if not api_key:
        if is_local_provider:
            api_key = provider
        else:
            raise ValueError(
                "API key not configured. Set SKENE_API_KEY environment variable "
                "or add api_key to ~/.config/skene/config"
            )

    return create_llm_client(provider, SecretStr(api_key), model)


async def analyze_tech_stack(
    path: str,
    cache: AnalysisCache,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Analyze the technology stack of a codebase.

    Detects framework, language, database, authentication, deployment, etc.
    Results are cached independently from other analysis phases.

    Args:
        path: Absolute path to the repository
        cache: Analysis cache instance
        force_refresh: Skip cache and force re-analysis

    Returns:
        Tech stack data with framework, language, database, etc.
    """
    from skene.analyzers import TechStackAnalyzer
    from skene.codebase import CodebaseExplorer

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    # Check phase cache
    if not force_refresh:
        cached = await cache.get_phase(repo_path, "tech_stack")
        if cached:
            return {
                "tech_stack": cached,
                "cached": True,
            }

    codebase = CodebaseExplorer(repo_path)
    llm = _get_llm_client()
    analyzer = TechStackAnalyzer()

    result = await analyzer.run(
        codebase=codebase,
        llm=llm,
        request="Detect the technology stack",
    )

    if not result.success:
        raise RuntimeError(f"Tech stack analysis failed: {result.error}")

    tech_stack = result.data.get("tech_stack", {})

    # Cache the result
    await cache.set_phase(repo_path, "tech_stack", tech_stack)

    return {
        "tech_stack": tech_stack,
        "cached": False,
    }


async def analyze_product_overview(
    path: str,
    cache: AnalysisCache,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Extract product overview from README and documentation.

    Extracts product name, tagline, description, value proposition, etc.
    Results are cached independently from other analysis phases.

    Args:
        path: Absolute path to the repository
        cache: Analysis cache instance
        force_refresh: Skip cache and force re-analysis

    Returns:
        Product overview data
    """
    from skene.analyzers.prompts import PRODUCT_OVERVIEW_PROMPT
    from skene.codebase import CodebaseExplorer
    from skene.manifest import ProductOverview
    from skene.strategies.steps import AnalyzeStep, ReadFilesStep, SelectFilesStep

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    # Check phase cache
    if not force_refresh:
        cached = await cache.get_phase(repo_path, "product_overview")
        if cached:
            return {
                "product_overview": cached,
                "cached": True,
            }

    codebase = CodebaseExplorer(repo_path)
    llm = _get_llm_client()

    # Run the Phase 2 steps from DocsAnalyzer
    from skene.strategies import MultiStepStrategy

    analyzer = MultiStepStrategy(
        steps=[
            SelectFilesStep(
                prompt="Select documentation files for product overview. "
                "Look for README, docs, and package descriptions.",
                patterns=[
                    "README.md",
                    "README*.md",
                    "readme.md",
                    "docs/*.md",
                    "docs/**/*.md",
                    "package.json",
                    "pyproject.toml",
                    "Cargo.toml",
                ],
                max_files=8,
                output_key="overview_files",
            ),
            ReadFilesStep(
                source_key="overview_files",
                output_key="overview_contents",
            ),
            AnalyzeStep(
                prompt=PRODUCT_OVERVIEW_PROMPT,
                output_schema=ProductOverview,
                output_key="product_overview",
                source_key="overview_contents",
            ),
        ]
    )

    result = await analyzer.run(
        codebase=codebase,
        llm=llm,
        request="Extract product overview from documentation",
    )

    if not result.success:
        raise RuntimeError(f"Product overview analysis failed: {result.error}")

    product_overview = result.data.get("product_overview", {})

    # Cache the result
    await cache.set_phase(repo_path, "product_overview", product_overview)

    return {
        "product_overview": product_overview,
        "cached": False,
    }


async def analyze_industry(
    path: str,
    cache: AnalysisCache,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Classify the industry/market vertical of a codebase.

    Analyzes README and documentation to determine the product's industry,
    sub-verticals, and business model tags.
    Results are cached independently from other analysis phases.

    Args:
        path: Absolute path to the repository
        cache: Analysis cache instance
        force_refresh: Skip cache and force re-analysis

    Returns:
        Industry classification data with primary, secondary, confidence, evidence
    """
    from skene.analyzers.prompts import INDUSTRY_PROMPT
    from skene.codebase import CodebaseExplorer
    from skene.manifest import IndustryInfo
    from skene.strategies.steps import AnalyzeStep, ReadFilesStep, SelectFilesStep

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    # Check phase cache
    if not force_refresh:
        cached = await cache.get_phase(repo_path, "industry")
        if cached:
            return {
                "industry": cached,
                "cached": True,
            }

    codebase = CodebaseExplorer(repo_path)
    llm = _get_llm_client()

    from skene.strategies import MultiStepStrategy

    analyzer = MultiStepStrategy(
        steps=[
            SelectFilesStep(
                prompt="Select documentation and package metadata files for industry classification. "
                "Look for README, docs, and package descriptors that describe what the product does.",
                patterns=[
                    "README.md",
                    "README*.md",
                    "readme.md",
                    "docs/*.md",
                    "docs/**/*.md",
                    "package.json",
                    "pyproject.toml",
                    "Cargo.toml",
                    "go.mod",
                ],
                max_files=10,
                output_key="industry_files",
            ),
            ReadFilesStep(
                source_key="industry_files",
                output_key="industry_contents",
            ),
            AnalyzeStep(
                prompt=INDUSTRY_PROMPT,
                output_schema=IndustryInfo,
                output_key="industry",
                source_key="industry_contents",
            ),
        ]
    )

    result = await analyzer.run(
        codebase=codebase,
        llm=llm,
        request="Classify the industry/market vertical",
    )

    if not result.success:
        raise RuntimeError(f"Industry classification failed: {result.error}")

    industry = result.data.get("industry", {})

    # Cache the result
    await cache.set_phase(repo_path, "industry", industry)

    return {
        "industry": industry,
        "cached": False,
    }


async def analyze_growth_hubs(
    path: str,
    cache: AnalysisCache,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Identify growth hubs (viral/growth features) in the codebase.

    Finds features with growth potential like invitations, sharing, referrals, etc.
    Results are cached independently from other analysis phases.

    Args:
        path: Absolute path to the repository
        cache: Analysis cache instance
        force_refresh: Skip cache and force re-analysis

    Returns:
        Growth hubs data with identified features
    """
    from skene.analyzers.prompts import GROWTH_FEATURES_PROMPT
    from skene.codebase import CodebaseExplorer
    from skene.strategies.steps import AnalyzeStep, ReadFilesStep, SelectFilesStep

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    # Check phase cache
    if not force_refresh:
        cached = await cache.get_phase(repo_path, "current_growth_features")
        if cached:
            return {
                "current_growth_features": cached,
                "cached": True,
            }

    codebase = CodebaseExplorer(repo_path)
    llm = _get_llm_client()

    # Run the Phase 2 steps from ManifestAnalyzer
    from skene.strategies import MultiStepStrategy

    analyzer = MultiStepStrategy(
        steps=[
            SelectFilesStep(
                prompt="Select source files with potential growth features. "
                "Look for user management, invitations, sharing, payments, "
                "analytics, onboarding, and engagement features.",
                patterns=[
                    "**/*.py",
                    "**/*.ts",
                    "**/*.tsx",
                    "**/*.js",
                    "**/routes/**/*",
                    "**/api/**/*",
                    "**/features/**/*",
                ],
                max_files=30,
                output_key="source_files",
            ),
            ReadFilesStep(
                source_key="source_files",
                output_key="source_contents",
            ),
            AnalyzeStep(
                prompt=GROWTH_FEATURES_PROMPT,
                output_key="current_growth_features",
                source_key="source_contents",
            ),
        ]
    )

    result = await analyzer.run(
        codebase=codebase,
        llm=llm,
        request="Identify growth hubs in the codebase",
    )

    if not result.success:
        raise RuntimeError(f"Growth features analysis failed: {result.error}")

    current_growth_features = result.data.get("current_growth_features", {})

    # Cache the result
    await cache.set_phase(repo_path, "current_growth_features", current_growth_features)

    return {
        "current_growth_features": current_growth_features,
        "cached": False,
    }


async def analyze_features(
    path: str,
    cache: AnalysisCache,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Document user-facing features from the codebase.

    Extracts feature information from source files.
    Results are cached independently from other analysis phases.

    Args:
        path: Absolute path to the repository
        cache: Analysis cache instance
        force_refresh: Skip cache and force re-analysis

    Returns:
        Features data
    """
    from skene.analyzers.prompts import FEATURES_PROMPT
    from skene.codebase import CodebaseExplorer
    from skene.strategies.steps import AnalyzeStep, ReadFilesStep, SelectFilesStep

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    # Check phase cache
    if not force_refresh:
        cached = await cache.get_phase(repo_path, "features")
        if cached:
            return {
                "features": cached,
                "cached": True,
            }

    codebase = CodebaseExplorer(repo_path)
    llm = _get_llm_client()

    # Run the Phase 3 steps from DocsAnalyzer (features part)
    from skene.strategies import MultiStepStrategy

    analyzer = MultiStepStrategy(
        steps=[
            SelectFilesStep(
                prompt="Select source files with user-facing features. "
                "Look for UI components, API endpoints, and feature implementations.",
                patterns=[
                    "**/*.py",
                    "**/*.ts",
                    "**/*.tsx",
                    "**/*.js",
                    "**/routes/**/*",
                    "**/api/**/*",
                    "**/features/**/*",
                    "**/components/**/*",
                    "**/pages/**/*",
                ],
                max_files=30,
                output_key="source_files",
            ),
            ReadFilesStep(
                source_key="source_files",
                output_key="source_contents",
            ),
            AnalyzeStep(
                prompt=FEATURES_PROMPT,
                output_key="features",
                source_key="source_contents",
            ),
        ]
    )

    result = await analyzer.run(
        codebase=codebase,
        llm=llm,
        request="Document user-facing features",
    )

    if not result.success:
        raise RuntimeError(f"Features analysis failed: {result.error}")

    features = result.data.get("features", {})

    # Cache the result
    await cache.set_phase(repo_path, "features", features)

    return {
        "features": features,
        "cached": False,
    }


# =============================================================================
# Tier 3: Generation Tools (5-15s each)
# =============================================================================


async def generate_manifest(
    path: str,
    cache: AnalysisCache,
    tech_stack: dict[str, Any] | None = None,
    product_overview: dict[str, Any] | None = None,
    industry: dict[str, Any] | None = None,
    current_growth_features: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
    auto_analyze: bool = True,
    product_docs: bool = False,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Generate a GrowthManifest from analysis results.

    Can use provided analysis results or auto-analyze missing phases.

    Args:
        path: Absolute path to the repository
        cache: Analysis cache instance
        tech_stack: Pre-computed tech stack (or auto-analyze if None)
        product_overview: Pre-computed product overview (or auto-analyze if None)
        industry: Pre-computed industry classification (or auto-analyze if None)
        current_growth_features: Pre-computed current growth features (or auto-analyze if None)
        features: Pre-computed features (or auto-analyze if None, only for product_docs)
        auto_analyze: If True, auto-analyze missing phases
        product_docs: If True, generate DocsManifest v2.0 (includes product_overview, features)
        force_refresh: Skip cache and force re-analysis

    Returns:
        Generated manifest data
    """
    from skene.analyzers.prompts import DOCS_MANIFEST_PROMPT, MANIFEST_PROMPT
    from skene.codebase import CodebaseExplorer
    from skene.manifest import DocsManifest, GrowthManifest
    from skene.strategies import MultiStepStrategy
    from skene.strategies.steps import GenerateStep

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    # Check manifest cache
    if not force_refresh:
        cached = await cache.get_phase(repo_path, "manifest")
        if cached:
            return {
                "manifest": cached,
                "cached": True,
            }

    # Try to load from cache if not provided
    if tech_stack is None:
        tech_stack = await cache.get_phase(repo_path, "tech_stack")
    if current_growth_features is None:
        current_growth_features = await cache.get_phase(repo_path, "current_growth_features")
    if industry is None:
        industry = await cache.get_phase(repo_path, "industry")
    if product_docs:
        if product_overview is None:
            product_overview = await cache.get_phase(repo_path, "product_overview")
        if features is None:
            features = await cache.get_phase(repo_path, "features")

    # Auto-analyze missing phases if enabled
    if auto_analyze:
        if tech_stack is None:
            result = await analyze_tech_stack(path, cache, force_refresh=force_refresh)
            tech_stack = result.get("tech_stack", {})

        if current_growth_features is None:
            result = await analyze_growth_hubs(path, cache, force_refresh=force_refresh)
            current_growth_features = result.get("current_growth_features", {})

        if industry is None:
            result = await analyze_industry(path, cache, force_refresh=force_refresh)
            industry = result.get("industry", {})

        if product_docs:
            if product_overview is None:
                result = await analyze_product_overview(path, cache, force_refresh=force_refresh)
                product_overview = result.get("product_overview", {})

            if features is None:
                result = await analyze_features(path, cache, force_refresh=force_refresh)
                features = result.get("features", {})
    else:
        # Validate required phase data is available
        missing_phases = []
        if not tech_stack:
            missing_phases.append("tech_stack (run analyze_tech_stack first)")
        if not current_growth_features:
            missing_phases.append("current_growth_features (run analyze_growth_hubs first)")
        # Industry is optional, don't require it
        if product_docs:
            if not product_overview:
                missing_phases.append("product_overview (run analyze_product_overview first)")
            if not features:
                missing_phases.append("features (run analyze_features first)")

        if missing_phases:
            raise ValueError(
                f"Missing required phase data: {', '.join(missing_phases)}. "
                "Run the phase analysis tools first to populate the cache."
            )

    codebase = CodebaseExplorer(repo_path)
    llm = _get_llm_client()

    # Build context for manifest generation
    context = {
        "tech_stack": tech_stack or {},
        "current_growth_features": current_growth_features or {},
        "industry": industry or {},
    }

    if product_docs:
        context["product_overview"] = product_overview or {}
        context["features"] = features or {}
        prompt = DOCS_MANIFEST_PROMPT
        output_schema = DocsManifest
    else:
        prompt = MANIFEST_PROMPT
        output_schema = GrowthManifest

    # Generate the manifest using GenerateStep
    analyzer = MultiStepStrategy(
        steps=[
            GenerateStep(
                prompt=prompt,
                output_schema=output_schema,
                include_context_keys=list(context.keys()),
                output_key="output",
            ),
        ]
    )

    # Inject pre-computed context
    result = await analyzer.run(
        codebase=codebase,
        llm=llm,
        request="Generate growth manifest",
        initial_context=context,
    )

    if not result.success:
        raise RuntimeError(f"Manifest generation failed: {result.error}")

    manifest_data = result.data.get("output", {})

    # Cache the result
    await cache.set_phase(repo_path, "manifest", manifest_data)

    return {
        "manifest": manifest_data,
        "cached": False,
    }


async def generate_growth_template_tool(
    path: str,
    cache: AnalysisCache,
    manifest_data: dict[str, Any] | None = None,
    business_type: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Generate a PLG growth template from a manifest.

    Results are cached independently from other analysis phases.

    Args:
        path: Absolute path to the repository (for context)
        cache: Analysis cache instance
        manifest_data: Manifest data to use (or read from disk/cache if None)
        business_type: Business type hint (e.g., 'b2b-saas', 'marketplace')
        force_refresh: Skip cache and force re-generation

    Returns:
        Generated growth template data
    """
    from skene.templates import generate_growth_template

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    # Check cache first
    if not force_refresh:
        cached = await cache.get_phase(repo_path, "growth_template")
        if cached:
            return {
                "template": cached,
                "cached": True,
            }

    # If no manifest provided, try to load from cache or disk
    if manifest_data is None:
        manifest_data = await cache.get_phase(repo_path, "manifest")
        if manifest_data is None:
            manifest_result = await get_manifest(path)
            if not manifest_result.get("exists"):
                raise ValueError("No manifest found. Run generate_manifest first.")
            manifest_data = manifest_result.get("manifest", {})

    llm = _get_llm_client()
    template = await generate_growth_template(llm, manifest_data, business_type)

    # Cache the result
    await cache.set_phase(repo_path, "growth_template", template)

    return {
        "template": template,
        "cached": False,
    }


async def write_analysis_outputs(
    path: str,
    cache: AnalysisCache,
    manifest_data: dict[str, Any] | None = None,
    template_data: dict[str, Any] | None = None,
    product_docs: bool = False,
) -> dict[str, Any]:
    """Write analysis outputs to disk.

    This is a pure I/O operation (<1s) - no LLM calls. Reads data from cache
    if not explicitly provided.

    Writes:
    - growth-manifest.json
    - product-docs.md (if product_docs=True)
    - growth-template.json (if available in cache or provided)

    IMPORTANT: Run generate_manifest and generate_growth_template first to
    populate the cache before calling this tool.

    Args:
        path: Absolute path to the repository
        cache: Analysis cache instance
        manifest_data: Manifest data to write (or read from cache/disk if None)
        template_data: Template data to write (or read from cache if None)
        product_docs: Generate product-docs.md

    Returns:
        Paths to written files
    """
    from skene.templates import write_growth_template_outputs

    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    # If no manifest provided, try to load from cache or disk
    if manifest_data is None:
        manifest_data = await cache.get_phase(repo_path, "manifest")
        if manifest_data is None:
            manifest_result = await get_manifest(path)
            if not manifest_result.get("exists"):
                raise ValueError("No manifest found. Run generate_manifest first to populate the cache.")
            manifest_data = manifest_result.get("manifest", {})

    # If no template provided, try to load from cache
    if template_data is None:
        template_data = await cache.get_phase(repo_path, "growth_template")

    output_dir = repo_path / "skene-context"
    output_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []

    # Write manifest JSON
    manifest_path = output_dir / "growth-manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2, default=_json_serializer))
    written_files.append(str(manifest_path))

    # Write product docs if requested
    if product_docs:
        _write_product_docs(manifest_data, manifest_path)
        written_files.append(str(output_dir / "product-docs.md"))

    # Write template if available
    if template_data:
        json_path = write_growth_template_outputs(template_data, output_dir)
        written_files.append(str(json_path))

    return {
        "output_dir": str(output_dir),
        "written_files": written_files,
    }


def _write_product_docs(manifest_data: dict, manifest_path: Path) -> None:
    """Generate and save product documentation."""
    from skene.docs import DocsGenerator
    from skene.manifest import DocsManifest, GrowthManifest

    try:
        if manifest_data.get("version") == "2.0" or "product_overview" in manifest_data or "features" in manifest_data:
            manifest = DocsManifest.model_validate(manifest_data)
        else:
            manifest = GrowthManifest.model_validate(manifest_data)
    except Exception:
        return

    output_dir = manifest_path.parent
    product_docs_path = output_dir / "product-docs.md"

    try:
        generator = DocsGenerator()
        product_content = generator.generate_product_docs(manifest)
        product_docs_path.write_text(product_content)
    except Exception:
        pass


async def _write_growth_template(llm, manifest_data: dict, business_type: str | None = None) -> dict | None:
    """Generate and save the growth template."""
    from skene.templates import generate_growth_template, write_growth_template_outputs

    try:
        template_data = await generate_growth_template(llm, manifest_data, business_type)
        output_dir = Path("./skene-context")
        write_growth_template_outputs(template_data, output_dir)
        return template_data
    except Exception:
        return None


async def get_manifest(path: str) -> dict[str, Any]:
    """Retrieve an existing manifest from disk.

    Args:
        path: Absolute path to the repository

    Returns:
        Manifest data if exists, or info that no manifest was found
    """
    repo_path = Path(path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")

    # Look for manifest in standard locations (same as CLI)
    manifest_locations = [
        repo_path / "skene-context" / "growth-manifest.json",
        repo_path / "growth-manifest.json",
        repo_path / ".skene" / "manifest.json",
    ]

    for manifest_path in manifest_locations:
        if manifest_path.exists():
            try:
                manifest_data = json.loads(manifest_path.read_text())
                return {
                    "manifest": manifest_data,
                    "manifest_path": str(manifest_path),
                    "exists": True,
                }
            except json.JSONDecodeError as e:
                raise ValueError(f"Manifest file is corrupted: {e}. Run analyze_codebase to regenerate.")

    return {
        "manifest": None,
        "manifest_path": str(repo_path / "skene-context" / "growth-manifest.json"),
        "exists": False,
        "message": "No manifest found. Run analyze_codebase to generate one.",
    }


async def clear_cache(cache: AnalysisCache, path: str | None = None) -> dict[str, Any]:
    """Clear cached analysis results.

    Args:
        cache: Analysis cache instance
        path: Optional path to clear cache for. If None, clears all cache.

    Returns:
        Number of entries cleared
    """
    if path:
        repo_path = Path(path).resolve()
        if not repo_path.exists():
            raise ValueError(f"Path does not exist: {repo_path}")
        cleared = await cache.clear(repo_path)
    else:
        cleared = await cache.clear()

    return {
        "cleared": cleared,
        "path": path,
        "message": f"Cleared {cleared} cache entries" + (f" for {path}" if path else ""),
    }
