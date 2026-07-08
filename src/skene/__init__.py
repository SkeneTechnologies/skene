"""
skene: PLG analysis toolkit for codebases.

Analyses a codebase and its SQL schema to produce a validated
``journey.yaml`` (see :mod:`skene.core.journey`).
"""

from skene.codebase import (
    DEFAULT_EXCLUDE_FOLDERS,
    CodebaseExplorer,
    build_directory_tree,
)
from skene.config import Config, load_config
from skene.llm import LLMClient, create_llm_client

__version__ = "0.5.1"

__all__ = [
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
]
