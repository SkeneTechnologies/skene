"""Orchestrator: iterates the benchmark matrix and manages output directories.

Combos are interleaved by provider to reduce the likelihood of hitting
rate/quota limits from a single provider.
"""

import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from loguru import logger

from benchmarks.runner.models import BenchmarkConfig, CodebaseConfig, ModelConfig, PipelineResult, StepMetadata
from benchmarks.runner.pipeline import run_pipeline


def create_timestamped_results_dir(base_path: Path) -> Path:
    """Create a timestamped results directory."""
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    results_dir = base_path / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def _interleave_by_provider(
    combos: list[tuple[CodebaseConfig, ModelConfig, int]],
) -> list[tuple[CodebaseConfig, ModelConfig, int]]:
    """Reorder combos so consecutive runs use different providers.

    Groups combos by provider, then round-robins across groups.
    This spreads API calls across providers and reduces quota pressure.
    """
    by_provider: dict[str, list[tuple[CodebaseConfig, ModelConfig, int]]] = defaultdict(list)
    for combo in combos:
        by_provider[combo[1].provider].append(combo)

    queues = list(by_provider.values())
    interleaved: list[tuple[CodebaseConfig, ModelConfig, int]] = []
    while queues:
        next_round = []
        for q in queues:
            interleaved.append(q.pop(0))
            if q:
                next_round.append(q)
        queues = next_round

    return interleaved


def run_benchmark_matrix(
    config: BenchmarkConfig,
    api_keys: dict[str, str],
    output_base_dir: Path,
    resume: bool = False,
) -> list[PipelineResult]:
    """Run the full benchmark matrix: codebase x model x run_number.

    Combos are interleaved by provider to avoid hammering a single
    provider's API consecutively.

    Args:
        config: Validated benchmark configuration.
        api_keys: Resolved API keys (env var name -> value).
        output_base_dir: Timestamped results directory.

    Returns:
        List of PipelineResult for each combo.
    """
    # Build full combo list
    combos: list[tuple[CodebaseConfig, ModelConfig, int]] = []
    for codebase in config.codebases:
        for model_cfg in config.models:
            for run_num in range(1, config.settings.runs_per_combo + 1):
                combos.append((codebase, model_cfg, run_num))

    # Interleave by provider
    combos = _interleave_by_provider(combos)

    results: list[PipelineResult] = []
    total = len(combos)

    for i, (codebase, model_cfg, run_num) in enumerate(combos, 1):
        api_key = api_keys[model_cfg.api_key_env]
        logger.info(f"[{i}/{total}] {codebase.name} / {model_cfg.name} / run-{run_num}")

        output_dir = output_base_dir / codebase.name / model_cfg.name / f"run-{run_num}"

        if resume and (output_dir / "metadata.json").exists():
            logger.info("  SKIP (already exists)")
            result = _load_single_result(output_dir, codebase.name, model_cfg.name, run_num)
            results.append(result)
            continue

        result = run_pipeline(
            codebase_path=codebase.path,
            codebase_name=codebase.name,
            provider=model_cfg.provider,
            model=model_cfg.model,
            model_name=model_cfg.name,
            api_key=api_key,
            output_dir=output_dir,
            run_number=run_num,
        )
        results.append(result)

        if result.success:
            logger.info(f"  -> Success ({sum(s.duration_seconds for s in result.steps):.1f}s total)")
        else:
            logger.warning(f"  -> Failed: {result.error_message}")

        # Delay between calls to avoid hitting rate/quota limits
        delay = config.settings.delay_between_calls
        if delay > 0 and i < total:
            logger.info(f"  Waiting {delay}s before next call...")
            time.sleep(delay)

    return results


def load_results_from_directory(results_dir: Path) -> list[PipelineResult]:
    """Reconstruct PipelineResult objects from an existing results directory.

    Walks the directory structure: <results_dir>/<codebase>/<model>/run-<n>/
    and rebuilds PipelineResult from metadata.json and output files.

    Args:
        results_dir: Path to a timestamped results directory.

    Returns:
        List of reconstructed PipelineResult objects.
    """
    results: list[PipelineResult] = []

    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    # Walk: <codebase>/<model>/run-<n>/
    for codebase_dir in sorted(results_dir.iterdir()):
        if not codebase_dir.is_dir() or codebase_dir.name.startswith("."):
            continue
        # Skip report files at the top level
        if codebase_dir.name in ("summary.json", "summary.md"):
            continue

        codebase_name = codebase_dir.name

        for model_dir in sorted(codebase_dir.iterdir()):
            if not model_dir.is_dir():
                continue

            model_name = model_dir.name

            for run_dir in sorted(model_dir.iterdir()):
                if not run_dir.is_dir() or not run_dir.name.startswith("run-"):
                    continue

                try:
                    run_number = int(run_dir.name.split("-", 1)[1])
                except (ValueError, IndexError):
                    logger.warning(f"Skipping unrecognized run dir: {run_dir}")
                    continue

                result = _load_single_result(run_dir, codebase_name, model_name, run_number)
                results.append(result)

    logger.info(f"Loaded {len(results)} result(s) from {results_dir}")
    return results


def _load_single_result(
    run_dir: Path,
    codebase_name: str,
    model_name: str,
    run_number: int,
) -> PipelineResult:
    """Load a single PipelineResult from a run directory."""
    metadata_path = run_dir / "metadata.json"
    steps: list[StepMetadata] = []
    provider = "unknown"
    model_id = "unknown"

    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)

        for step_data in metadata.get("steps", []):
            steps.append(StepMetadata(
                step_name=step_data["step_name"],
                exit_code=step_data["exit_code"],
                duration_seconds=step_data["duration_seconds"],
                command=step_data.get("command", []),
                success=step_data["success"],
            ))

            # Extract provider and model_id from the command args
            cmd = step_data.get("command", [])
            for i, arg in enumerate(cmd):
                if arg == "--provider" and i + 1 < len(cmd):
                    provider = cmd[i + 1]
                elif arg == "--model" and i + 1 < len(cmd):
                    model_id = cmd[i + 1]

    # Determine success: all steps must have succeeded
    all_succeeded = len(steps) > 0 and all(s.success for s in steps)
    # Also check we got all 3 steps
    pipeline_complete = len(steps) == 3 and all_succeeded

    error_message = None
    if not pipeline_complete:
        failed = [s.step_name for s in steps if not s.success]
        if failed:
            error_message = f"Failed steps: {', '.join(failed)}"
        elif len(steps) < 3:
            error_message = f"Pipeline incomplete: only {len(steps)} of 3 steps ran"

    return PipelineResult(
        codebase_name=codebase_name,
        model_name=model_name,
        provider=provider,
        model_id=model_id,
        run_number=run_number,
        output_dir=run_dir,
        steps=steps,
        success=pipeline_complete,
        error_message=error_message,
    )
