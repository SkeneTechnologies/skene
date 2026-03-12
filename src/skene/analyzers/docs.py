"""
Documentation-focused analyzer using MultiStepStrategy.

Extends growth manifest analysis to include real product documentation
fields like product_overview and features.
"""

from typing import Any

from skene.analyzers.prompts import (
    FEATURES_PROMPT,
    INDUSTRY_PROMPT,
    PRODUCT_OVERVIEW_PROMPT,
    TECH_STACK_PROMPT,
    build_docs_manifest_prompt,
    build_growth_features_prompt,
)
from skene.manifest import (
    DocsManifest,
    IndustryInfo,
    ProductOverview,
    TechStack,
)
from skene.strategies import MultiStepStrategy
from skene.strategies.steps import (
    AnalyzeStep,
    GenerateStep,
    ReadFilesStep,
    SelectFilesStep,
)


class DocsAnalyzer(MultiStepStrategy):
    """
    Documentation analyzer that produces a DocsManifest.

    This analyzer extends the base growth manifest with documentation
    fields by running in 5 phases:

    1. Tech stack detection (config files)
    2. Product overview extraction (README, docs)
    3. Industry classification (reuses docs from phase 2)
    4. Feature documentation + current growth features (source files)
    5. Final manifest generation

    Example:
        analyzer = DocsAnalyzer()
        result = await analyzer.run(
            codebase=CodebaseExplorer("/path/to/repo"),
            llm=create_llm_client(),
            request="Generate documentation for this project",
        )
        manifest = DocsManifest.model_validate(result.data.get("output"))
    """

    def __init__(self, existing_growth_loops: list[dict[str, Any]] | None = None):
        """Initialize the docs analyzer with all analysis steps."""
        self.existing_growth_loops = existing_growth_loops or []

        # Format existing loops for prompt inclusion
        from skene.growth_loops.storage import format_growth_loops_summary

        loops_summary = format_growth_loops_summary(self.existing_growth_loops)

        # Build prompts with existing loops context
        growth_features_prompt = build_growth_features_prompt(loops_summary)
        docs_manifest_prompt = build_docs_manifest_prompt(loops_summary)

        super().__init__(
            steps=[
                # Phase 1: Tech Stack Detection
                SelectFilesStep(
                    prompt="Select configuration files for tech stack detection. "
                    "Include package managers, framework configs, and dependency files.",
                    patterns=[
                        "package.json",
                        "requirements.txt",
                        "pyproject.toml",
                        "Cargo.toml",
                        "go.mod",
                        "Gemfile",
                        "*.config.js",
                        "*.config.ts",
                        "tsconfig.json",
                        "docker-compose.yml",
                        "Dockerfile",
                    ],
                    max_files=10,
                    output_key="config_files",
                ),
                ReadFilesStep(
                    source_key="config_files",
                    output_key="config_contents",
                ),
                AnalyzeStep(
                    prompt=TECH_STACK_PROMPT,
                    output_schema=TechStack,
                    output_key="tech_stack",
                    source_key="config_contents",
                ),
                # Phase 2: Product Overview Extraction
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
                # Phase 3: Industry Classification (reuses overview_contents)
                AnalyzeStep(
                    prompt=INDUSTRY_PROMPT,
                    output_schema=IndustryInfo,
                    output_key="industry",
                    source_key="overview_contents",
                ),
                # Phase 4: Feature Documentation + Current Growth Features
                SelectFilesStep(
                    prompt="Select source files with growth features. "
                    "Look for user management, invitations, sharing, payments, analytics.",
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
                    prompt=FEATURES_PROMPT,
                    output_key="features",
                    source_key="source_contents",
                ),
                AnalyzeStep(
                    prompt=growth_features_prompt,
                    output_key="current_growth_features",
                    source_key="source_contents",
                ),
                # Phase 5: Final Manifest Generation
                GenerateStep(
                    prompt=docs_manifest_prompt,
                    output_schema=DocsManifest,
                    include_context_keys=[
                        "tech_stack",
                        "product_overview",
                        "industry",
                        "features",
                        "current_growth_features",
                    ],
                    output_key="output",
                ),
            ]
        )
