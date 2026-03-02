"""Benchmark runner entry point.

Usage:
    uv run benchmarks/run.py
    uv run benchmarks/run.py --config benchmarks/config.toml
    uv run benchmarks/run.py --skip-judge
    uv run benchmarks/run.py --evaluate-only results/2025-02-16T14-30-00
    uv run benchmarks/run.py --resume results/2025-02-16T14-30-00
"""

import os
import sys
from pathlib import Path

import typer
from loguru import logger

# Ensure project root is on sys.path so `benchmarks.*` imports resolve
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Configure loguru: stderr, concise format
logger.remove()
logger.add(sys.stderr, format="{time:HH:mm:ss} | {level:<7} | {message}", level="INFO")

app = typer.Typer(add_completion=False)


@app.command()
def main(
    config: Path = typer.Option(
        Path("benchmarks/config.toml"),
        "--config",
        help="Path to benchmark config TOML file",
    ),
    skip_judge: bool = typer.Option(
        False,
        "--skip-judge",
        help="Skip LLM-as-judge evaluation",
    ),
    evaluate_only: Path | None = typer.Option(
        None,
        "--evaluate-only",
        help="Re-evaluate existing results directory (skip pipeline, re-run checks and report)",
    ),
    resume: Path | None = typer.Option(
        None,
        "--resume",
        help="Resume a previous run: re-run only missing benchmarks, skip existing ones",
    ),
) -> None:
    """Run the skene-growth benchmark suite."""
    from benchmarks.evaluation.llm_judge import evaluate_with_llm_judge
    from benchmarks.evaluation.report import generate_report
    from benchmarks.evaluation.structural import evaluate_structural
    from benchmarks.runner.models import load_benchmark_config, resolve_api_keys
    from benchmarks.runner.orchestrator import (
        create_timestamped_results_dir,
        load_results_from_directory,
        run_benchmark_matrix,
    )

    if evaluate_only and resume:
        logger.error("--evaluate-only and --resume are mutually exclusive")
        raise typer.Exit(1)

    if evaluate_only:
        # Re-evaluate existing results without re-running the pipeline
        results_dir = evaluate_only
        logger.info(f"Re-evaluating existing results from {results_dir}")

        try:
            results = load_results_from_directory(results_dir)
        except FileNotFoundError as e:
            logger.error(str(e))
            raise typer.Exit(1)

        if not results:
            logger.error(f"No results found in {results_dir}")
            raise typer.Exit(1)

        # Load config for ground truth paths (if config exists)
        bench_config = None
        if config.exists():
            try:
                bench_config = load_benchmark_config(config)
                logger.info(f"Loaded config from {config} (for ground truth)")
            except Exception as e:
                logger.warning(f"Could not load config for ground truth: {e}")
    elif resume:
        # Resume a previous run: re-run only missing benchmarks
        results_dir = resume
        logger.info(f"Resuming previous run from {results_dir}")

        if not results_dir.exists():
            logger.error(f"Results directory not found: {results_dir}")
            raise typer.Exit(1)

        # Load config
        logger.info(f"Loading config from {config}")
        try:
            bench_config = load_benchmark_config(config)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise typer.Exit(1)

        logger.info(
            f"Config: {len(bench_config.codebases)} codebase(s), "
            f"{len(bench_config.models)} model(s), "
            f"{bench_config.settings.runs_per_combo} run(s) per combo"
        )

        # Resolve API keys
        try:
            api_keys = resolve_api_keys(bench_config)
        except ValueError as e:
            logger.error(str(e))
            raise typer.Exit(1)

        logger.info(f"Resolved {len(api_keys)} API key(s)")

        # Run benchmark matrix with resume=True
        results = run_benchmark_matrix(bench_config, api_keys, results_dir, resume=True)

    else:
        # Full pipeline run
        # Load config
        logger.info(f"Loading config from {config}")
        try:
            bench_config = load_benchmark_config(config)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise typer.Exit(1)

        logger.info(
            f"Config: {len(bench_config.codebases)} codebase(s), "
            f"{len(bench_config.models)} model(s), "
            f"{bench_config.settings.runs_per_combo} run(s) per combo"
        )

        # Resolve API keys
        try:
            api_keys = resolve_api_keys(bench_config)
        except ValueError as e:
            logger.error(str(e))
            raise typer.Exit(1)

        logger.info(f"Resolved {len(api_keys)} API key(s)")

        # Create results directory
        results_base = Path("benchmarks/results")
        results_dir = create_timestamped_results_dir(results_base)
        logger.info(f"Results directory: {results_dir}")

        # Run benchmark matrix
        results = run_benchmark_matrix(bench_config, api_keys, results_dir)

    # Structural evaluation
    logger.info("Running structural evaluation...")
    structural_evals = [evaluate_structural(r) for r in results]

    # Factual evaluation (only for codebases with ground truth)
    from benchmarks.evaluation.factual import evaluate_factual
    from benchmarks.evaluation.ground_truth import load_ground_truth
    from benchmarks.evaluation.models import FactualEvaluation

    ground_truth_map: dict[str, Path] = {}
    if bench_config:
        for cb in bench_config.codebases:
            if cb.ground_truth:
                ground_truth_map[cb.name] = cb.ground_truth

    factual_evals: list[FactualEvaluation] = []
    if ground_truth_map:
        logger.info(f"Running factual evaluation for {len(ground_truth_map)} codebase(s) with ground truth...")
        codebase_paths = {cb.name: cb.path for cb in bench_config.codebases} if bench_config else {}
        for r in results:
            gt_path = ground_truth_map.get(r.codebase_name)
            if gt_path:
                gt = load_ground_truth(gt_path)
                factual_eval = evaluate_factual(r, gt, codebase_path=codebase_paths.get(r.codebase_name))
                factual_evals.append(factual_eval)
    else:
        logger.info("No ground truth files configured, skipping factual evaluation")

    # LLM judge evaluation (optional)
    if not skip_judge and bench_config:
        judge_key_env = bench_config.settings.judge_api_key_env
        judge_api_key = os.environ.get(judge_key_env)
        for r in results:
            evaluate_with_llm_judge(
                r,
                judge_provider=bench_config.settings.judge_provider,
                judge_model=bench_config.settings.judge_model,
                judge_api_key=judge_api_key,
            )
    elif not skip_judge and not bench_config:
        logger.warning("Skipping LLM judge: no config loaded (needed for judge settings)")

    # Generate report
    json_path, md_path = generate_report(results, structural_evals, results_dir, factual_evals)

    # Summary
    successful = sum(1 for r in results if r.success)
    logger.info(f"Done! {successful}/{len(results)} runs succeeded")
    logger.info(f"Report: {md_path}")
    logger.info(f"Data:   {json_path}")

    # Print to stdout so it's visible even when stderr is noisy
    print(f"\n{'=' * 60}")
    print(f"Benchmark complete: {successful}/{len(results)} runs succeeded")
    print(f"Report: {md_path}")
    print(f"Data:   {json_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    app()
