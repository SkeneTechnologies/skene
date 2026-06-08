"""Journey analysis pipeline (heuristic by default, LLM-backed when configured).

Reimplements the shape of the reference ``analyze-journey`` command:
extract candidates → merge → classify into the seven canonical stages → assemble a
validated ``Journey``. Each LLM-driven step has a deterministic default and an LLM backend
(see ``llm.py`` / ``code_agent.py`` / ``branch_agent.py``); ``factory.build_pipeline``
selects between them from settings.
"""

from __future__ import annotations

from .branch_agent import LlmBrancher
from .candidate import CandidateMilestone
from .classify import Classifier, HeuristicClassifier, LlmClassifier
from .code_agent import LlmCodeAgent
from .extract import CandidateExtractor, HeuristicCodeScanner
from .factory import build_pipeline
from .llm import LlmAnalysisError
from .pipeline import Brancher, JourneyPipeline, JourneyPipelineAnalyzer
from .stages import STAGES, StageDef

__all__ = [
    "CandidateMilestone",
    "LlmAnalysisError",
    "Classifier",
    "HeuristicClassifier",
    "LlmClassifier",
    "CandidateExtractor",
    "HeuristicCodeScanner",
    "LlmCodeAgent",
    "LlmBrancher",
    "Brancher",
    "JourneyPipeline",
    "JourneyPipelineAnalyzer",
    "build_pipeline",
    "STAGES",
    "StageDef",
]
