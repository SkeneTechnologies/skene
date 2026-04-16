"""
Full manifest analyzer using MultiStepStrategy.

Combines tech stack and growth features analysis to produce
a complete GrowthManifest.
"""

from skene.analyzers.prompts import (
    INDUSTRY_PROMPT,
    REVENUE_LEAKAGE_PROMPT,
    TECH_STACK_PROMPT,
    build_growth_features_prompt,
    build_manifest_prompt,
)
from skene.manifest import GrowthManifest, IndustryInfo, TechStack
from skene.strategies import MultiStepStrategy
from skene.strategies.steps import (
    AnalyzeStep,
    GenerateStep,
    ReadFilesStep,
    SelectFilesStep,
)


class ManifestAnalyzer(MultiStepStrategy):
    """
    Full-pipeline analyzer that produces a complete GrowthManifest.

    This analyzer runs in four phases:
    1. Tech stack detection (config files)
    2. Current growth features identification (source files)
    3. Revenue leakage analysis (pricing/payment files)
    4. Industry classification (docs/README)
    5. Manifest generation (combining results + growth opportunities)

    Example:
        analyzer = ManifestAnalyzer()
        result = await analyzer.run(
            codebase=CodebaseExplorer("/path/to/repo"),
            llm=create_llm_client(),
            request="Generate a growth manifest for this project",
        )
        manifest = GrowthManifest.model_validate(result.data.get("output"))
    """

    def __init__(self, engine_summary: str = ""):
        """Initialize the manifest analyzer with all analysis steps."""
        # Build prompts with existing engine context
        growth_features_prompt = build_growth_features_prompt(engine_summary)
        manifest_prompt = build_manifest_prompt(engine_summary)

        super().__init__(
            steps=[
                # Phase 1: Detect tech stack
                SelectFilesStep(
                    prompt="Select configuration files and representative source files for tech stack detection. "
                    "Include package managers, framework configs, dependency files, "
                    "and a few source files to identify the language.",
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
                        # Include source files to help identify language
                        "**/*.py",
                        "**/*.js",
                        "**/*.ts",
                        "**/*.tsx",
                        "**/*.go",
                        "**/*.rs",
                        "**/*.rb",
                    ],
                    max_files=15,
                    output_key="config_files",
                ),
                ReadFilesStep(
                    source_key="config_files",
                    output_key="file_contents",
                ),
                AnalyzeStep(
                    prompt=TECH_STACK_PROMPT,
                    output_schema=TechStack,
                    output_key="tech_stack",
                    source_key="file_contents",
                ),
                # Phase 2: Find current growth features
                # Note: file_contents will be overwritten, but tech_stack is preserved
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
                    output_key="file_contents",
                ),
                AnalyzeStep(
                    prompt=growth_features_prompt,
                    output_key="current_growth_features",
                    source_key="file_contents",
                ),
                # Phase 2.5: Analyze revenue leakage
                SelectFilesStep(
                    prompt="Select files related to pricing, payments, subscriptions, billing, "
                    "usage limits, feature flags, tier management, and monetization. "
                    "Look for payment processing, subscription logic, free tier restrictions, "
                    "upgrade prompts, and pricing configurations.",
                    patterns=[
                        "**/pricing/**/*",
                        "**/payment/**/*",
                        "**/billing/**/*",
                        "**/subscription/**/*",
                        "**/plan/**/*",
                        "**/tier/**/*",
                        "**/usage/**/*",
                        "**/limit/**/*",
                        "**/upgrade/**/*",
                        "**/monetization/**/*",
                        "**/stripe/**/*",
                        "**/paypal/**/*",
                    ],
                    max_files=20,
                    output_key="revenue_files",
                ),
                ReadFilesStep(
                    source_key="revenue_files",
                    output_key="revenue_file_contents",
                ),
                AnalyzeStep(
                    prompt=REVENUE_LEAKAGE_PROMPT,
                    output_key="revenue_leakage",
                    source_key="revenue_file_contents",
                ),
                # Phase 3: Industry classification
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
                    output_key="industry_file_contents",
                ),
                AnalyzeStep(
                    prompt=INDUSTRY_PROMPT,
                    output_schema=IndustryInfo,
                    output_key="industry",
                    source_key="industry_file_contents",
                ),
                # Phase 4: Generate final manifest
                GenerateStep(
                    prompt=manifest_prompt,
                    output_schema=GrowthManifest,
                    include_context_keys=["tech_stack", "current_growth_features", "revenue_leakage", "industry"],
                    output_key="output",
                ),
            ]
        )
