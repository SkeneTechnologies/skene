"""
Tech stack analyzer using MultiStepStrategy.

Detects the technology stack of a project by analyzing
configuration files like package.json, requirements.txt, etc.
"""

from skene.analyzers.prompts import TECH_STACK_PROMPT
from skene.manifest import TechStack
from skene.strategies import MultiStepStrategy
from skene.strategies.steps import (
    AnalyzeStep,
    ReadFilesStep,
    SelectFilesStep,
)


class TechStackAnalyzer(MultiStepStrategy):
    """
    Analyzer for detecting project technology stack.

    This analyzer examines configuration files to identify:
    - Framework (Next.js, FastAPI, Rails, etc.)
    - Language (Python, TypeScript, Go, etc.)
    - Database (PostgreSQL, MongoDB, etc.)
    - Authentication method
    - Deployment platform
    - Package manager

    Example:
        analyzer = TechStackAnalyzer()
        result = await analyzer.run(
            codebase=CodebaseExplorer("/path/to/repo"),
            llm=create_llm_client(),
            request="Detect the tech stack",
        )
        tech_stack = result.data.get("tech_stack")
    """

    def __init__(self):
        """Initialize the tech stack analyzer with predefined steps."""
        super().__init__(
            steps=[
                SelectFilesStep(
                    prompt="Select configuration files and representative source files "
                    "that reveal the technology stack. "
                    "Include package managers, framework configs, dependency files, "
                    "and a few source files to identify the language.",
                    patterns=[
                        "package.json",
                        "requirements.txt",
                        "pyproject.toml",
                        "Cargo.toml",
                        "go.mod",
                        "Gemfile",
                        "composer.json",
                        "*.config.js",
                        "*.config.ts",
                        "tsconfig.json",
                        "next.config.*",
                        "vite.config.*",
                        "docker-compose.yml",
                        "Dockerfile",
                        ".env.example",
                        "vercel.json",
                        "netlify.toml",
                        "fly.toml",
                        "render.yaml",
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
                    output_key="selected_files",
                ),
                ReadFilesStep(
                    source_key="selected_files",
                    output_key="file_contents",
                ),
                AnalyzeStep(
                    prompt=TECH_STACK_PROMPT,
                    output_schema=TechStack,
                    output_key="tech_stack",
                    source_key="file_contents",
                ),
            ]
        )
