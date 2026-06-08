"""Build a ``JourneyPipeline`` from settings, choosing the heuristic or LLM backend."""

from __future__ import annotations

import logging

from ..config import Settings
from .pipeline import JourneyPipeline

logger = logging.getLogger("skened.pipeline.factory")


def build_pipeline(settings: Settings) -> JourneyPipeline:
    if not settings.llm_enabled:
        logger.info("analysis backend: heuristic (offline)")
        return JourneyPipeline()

    if not settings.llm_model:
        raise ValueError(
            "analysis_backend='llm' requires SKENE_LLM_MODEL to be set "
            "(e.g. 'anthropic/claude-sonnet-4-6')."
        )

    # Imported here so litellm/LLM code is only touched when actually using the LLM backend.
    from .branch_agent import LlmBrancher
    from .classify import LlmClassifier
    from .code_agent import LlmCodeAgent
    from .llm import LiteLLMClient

    llm = LiteLLMClient(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
    )
    logger.info("analysis backend: llm (model=%s)", settings.llm_model)
    return JourneyPipeline(
        extractor=LlmCodeAgent(llm, max_turns=settings.llm_max_turns),
        classifier=LlmClassifier(llm, concurrency=settings.llm_classify_concurrency),
        brancher=LlmBrancher(llm),
    )
