"""
skene-growth: PLG analysis toolkit for codebases.

This library provides tools for analyzing codebases, detecting growth opportunities,
and generating documentation.
"""

from skene_growth.analyzers import (
    GrowthFeaturesAnalyzer,
    ManifestAnalyzer,
    TechStackAnalyzer,
)
from skene_growth.codebase import (
    DEFAULT_EXCLUDE_FOLDERS,
    CodebaseExplorer,
    build_directory_tree,
)
from skene_growth.config import Config, load_config
from skene_growth.docs import DocsGenerator, PSEOBuilder
from skene_growth.llm import LLMClient, create_llm_client
from skene_growth.manifest import (
    GrowthFeature,
    GrowthManifest,
    GrowthOpportunity,
    TechStack,
)
from skene_growth.planner import (
    Planner,
)
from skene_growth.strategies import (
    AnalysisContext,
    AnalysisMetadata,
    AnalysisResult,
    AnalysisStrategy,
    MultiStepStrategy,
)
from skene_growth.strategies.steps import (
    AnalysisStep,
    AnalyzeStep,
    GenerateStep,
    ReadFilesStep,
    SelectFilesStep,
)

__version__ = "0.2.1b1"

__all__ = [
    # Analyzers
    "TechStackAnalyzer",
    "GrowthFeaturesAnalyzer",
    "ManifestAnalyzer",
    # Manifest schemas
    "TechStack",
    "GrowthFeature",
    "GrowthOpportunity",
    "GrowthManifest",
    # Codebase
    "CodebaseExplorer",
    "build_directory_tree",
    "DEFAULT_EXCLUDE_FOLDERS",
    # Config
    "Config",
    "load_config",
    # LLM
    "LLMClient",
    "create_llm_client",
    # Strategies
    "AnalysisStrategy",
    "AnalysisResult",
    "AnalysisMetadata",
    "AnalysisContext",
    "MultiStepStrategy",
    # Steps
    "AnalysisStep",
    "SelectFilesStep",
    "ReadFilesStep",
    "AnalyzeStep",
    "GenerateStep",
    # Documentation
    "DocsGenerator",
    "PSEOBuilder",
    # Planner
    "Planner",
]
