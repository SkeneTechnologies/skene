"""
skene: PLG analysis toolkit for codebases.

This library provides tools for analyzing codebases, detecting growth opportunities,
and generating documentation.
"""

from skene.analyzers import (
    GrowthFeaturesAnalyzer,
    ManifestAnalyzer,
    TechStackAnalyzer,
)
from skene.codebase import (
    DEFAULT_EXCLUDE_FOLDERS,
    CodebaseExplorer,
    build_directory_tree,
)
from skene.config import Config, load_config
from skene.docs import DocsGenerator, PSEOBuilder
from skene.llm import LLMClient, create_llm_client
from skene.manifest import (
    GrowthFeature,
    GrowthManifest,
    GrowthOpportunity,
    TechStack,
)
from skene.planner import (
    Planner,
)
from skene.strategies import (
    AnalysisContext,
    AnalysisMetadata,
    AnalysisResult,
    AnalysisStrategy,
    MultiStepStrategy,
)
from skene.strategies.steps import (
    AnalysisStep,
    AnalyzeStep,
    GenerateStep,
    ReadFilesStep,
    SelectFilesStep,
)

__version__ = "0.4.0rc2"

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
