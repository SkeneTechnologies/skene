"""End-to-end orchestration for the agentic journey pipeline.

Steps:

    0. Specialize stages    ───┐
    1. Schema agent         ───┼── parallel (asyncio.gather)
    2. Code agent           ───┘
    3. Merge (deterministic)
    4. Classify (per-milestone LLM, parallel under a semaphore)
    5. Assemble (validated Journey)

KPI generation and connector inference are out of scope for v1, so the
emitted Journey has empty ``kpis`` per stage and an empty ``connectors``
list.

This module is provider-agnostic — it takes an :class:`LLMClient` and uses
only the abstractions in :mod:`skene.llm.agent_loop`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from skene.analyzers.journey.assemble import assemble_journey
from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.classify import classify_all
from skene.analyzers.journey.code_agent import run_code_agent
from skene.analyzers.journey.merge import merge_candidates
from skene.analyzers.journey.models import Journey
from skene.analyzers.journey.schema_agent import run_schema_agent
from skene.analyzers.journey.specialize import specialize_stages
from skene.analyzers.journey.stages import STAGES, StageDef
from skene.llm.base import LLMClient
from skene.output import status, warning


@dataclass
class JourneyPipelineConfig:
    """Inputs for :func:`run_journey_pipeline`.

    ``repo_root`` and ``schema_dir`` are both optional but at least one
    must be set — the caller (CLI) enforces this. Three modes:

    - **both**: full pipeline. Specialize + schema agent + code agent.
    - **code only** (``schema_dir is None``): skip schema agent.
    - **schema only** (``repo_root is None``): skip code agent AND skip
      stage specialization (no README to read). Stages stay canonical.
    """

    repo_root: Path | None
    schema_dir: Path | None
    product_name: str
    classify_concurrency: int = 8
    schema_max_turns: int = 150
    code_max_turns: int = 200
    specialize: bool = True

    def __post_init__(self) -> None:
        if self.repo_root is None and self.schema_dir is None:
            raise ValueError("JourneyPipelineConfig requires at least one of repo_root or schema_dir")


def _describe_mode(cfg: JourneyPipelineConfig) -> str:
    if cfg.repo_root is not None and cfg.schema_dir is not None:
        return "code+schema"
    if cfg.repo_root is not None:
        return "code-only"
    return "schema-only"


async def run_journey_pipeline(cfg: JourneyPipelineConfig, llm: LLMClient) -> Journey:
    """Run the full pipeline end-to-end and return a validated Journey."""
    mode = _describe_mode(cfg)
    status(f"Pipeline start: product={cfg.product_name} model={llm.get_model_name()} mode={mode}")
    if mode != "code+schema":
        warning(
            f"running in {mode} mode — the LLM has only half the evidence, "
            "so the journey is inherently less precise than a both-sources run"
        )

    schema_task: asyncio.Task[list[CandidateMilestone]] | None = None
    code_task: asyncio.Task[list[CandidateMilestone]] | None = None
    specialize_task: asyncio.Task[tuple[StageDef, ...]] | None = None

    if cfg.schema_dir is not None:
        schema_task = asyncio.create_task(
            run_schema_agent(
                cfg.schema_dir,
                llm=llm,
                max_turns=cfg.schema_max_turns,
            )
        )
    if cfg.repo_root is not None:
        code_task = asyncio.create_task(
            run_code_agent(
                cfg.repo_root,
                llm=llm,
                max_turns=cfg.code_max_turns,
            )
        )
    if cfg.specialize and cfg.repo_root is not None:
        specialize_task = asyncio.create_task(specialize_stages(cfg.repo_root, cfg.product_name, llm=llm))
    elif cfg.specialize and cfg.repo_root is None:
        status("Step 0: skipped (schema-only mode) — using canonical stages")
    else:
        status("Step 0: skipped (--no-specialize) — using canonical stages")

    running = [t for t in (schema_task, code_task, specialize_task) if t is not None]
    await asyncio.gather(*running)

    schema_candidates = schema_task.result() if schema_task is not None else []
    code_candidates = code_task.result() if code_task is not None else []
    stages = specialize_task.result() if specialize_task is not None else STAGES

    status(f"Steps 1+2 done: schema agent emitted {len(schema_candidates)}, code agent emitted {len(code_candidates)}")

    status("Step 3: merging candidates (deterministic)")
    merged = merge_candidates(schema_candidates, code_candidates)
    status(
        f"Step 3 done: merged {len(schema_candidates)} schema + {len(code_candidates)} "
        f"code → {len(merged)} unique candidates"
    )

    status(f"Step 4: classifying {len(merged)} candidates (concurrency={cfg.classify_concurrency})")
    classified = await classify_all(
        merged,
        llm=llm,
        concurrency=cfg.classify_concurrency,
        stages=stages,
    )
    by_stage: dict[str, int] = {}
    for cm in classified:
        if cm.stage_id:
            by_stage[cm.stage_id] = by_stage.get(cm.stage_id, 0) + 1
    status("Step 4 done: classification — " + (", ".join(f"{k}={v}" for k, v in sorted(by_stage.items())) or "(none)"))

    status("Step 5: assembling Journey")
    journey = assemble_journey(classified, product_name=cfg.product_name, stages=stages)
    status(
        f"Pipeline complete: stages={len(journey.stages)} milestones={sum(len(s.milestones) for s in journey.stages)}"
    )
    return journey
