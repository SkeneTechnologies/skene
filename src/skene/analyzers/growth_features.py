"""
Growth features analyzer using MultiStepStrategy.

Identifies current features and areas of a codebase with growth potential.
"""

from skene.analyzers.prompts import GROWTH_FEATURES_PROMPT
from skene.strategies import MultiStepStrategy
from skene.strategies.steps import (
    AnalyzeStep,
    ReadFilesStep,
    SelectFilesStep,
)


class GrowthFeaturesAnalyzer(MultiStepStrategy):
    """
    Analyzer for identifying current growth features in a codebase.

    Current growth features are features or areas that:
    - Enable viral growth (sharing, invitations, referrals)
    - Drive user engagement
    - Facilitate onboarding
    - Support monetization
    - Enable data-driven decisions

    Example:
        analyzer = GrowthFeaturesAnalyzer()
        result = await analyzer.run(
            codebase=CodebaseExplorer("/path/to/repo"),
            llm=create_llm_client(),
            request="Find growth opportunities",
        )
        features = result.data.get("current_growth_features", [])
    """

    def __init__(self):
        """Initialize the growth features analyzer with predefined steps."""
        super().__init__(
            steps=[
                SelectFilesStep(
                    prompt="Select source files that might contain growth-related features. "
                    "Look for: user management, invitations, sharing, payments, "
                    "analytics, onboarding, notifications, and engagement features.",
                    patterns=[
                        "**/*.py",
                        "**/*.ts",
                        "**/*.tsx",
                        "**/*.js",
                        "**/*.jsx",
                        "**/routes/**/*",
                        "**/api/**/*",
                        "**/features/**/*",
                        "**/components/**/*",
                        "**/pages/**/*",
                        "**/app/**/*",
                    ],
                    max_files=30,
                    output_key="selected_files",
                ),
                ReadFilesStep(
                    source_key="selected_files",
                    output_key="file_contents",
                ),
                AnalyzeStep(
                    prompt=GROWTH_FEATURES_PROMPT,
                    output_key="current_growth_features",
                    source_key="file_contents",
                ),
            ]
        )
