"""Pipeline runner: executes analyze -> plan -> build for a single combo."""

import json
import subprocess
import time
from pathlib import Path

from loguru import logger

from benchmarks.runner.models import PipelineResult, StepMetadata


def _build_analyze_command(
    codebase_path: Path,
    provider: str,
    model: str,
    api_key: str,
    output_dir: Path,
) -> list[str]:
    """Build the CLI command for the analyze step."""
    return [
        "uv",
        "run",
        "skene",
        "analyze",
        str(codebase_path),
        "--provider",
        provider,
        "--model",
        model,
        "--api-key",
        api_key,
        "--output",
        str(output_dir),
        "--no-fallback",
        "--debug",
    ]


def _build_plan_command(
    provider: str,
    model: str,
    api_key: str,
    context_dir: Path,
    output_file: Path,
) -> list[str]:
    """Build the CLI command for the plan step."""
    return [
        "uv",
        "run",
        "skene",
        "plan",
        "--context",
        str(context_dir),
        "--provider",
        provider,
        "--model",
        model,
        "--api-key",
        api_key,
        "--output",
        str(output_file),
        "--no-fallback",
        "--debug",
    ]


def _build_build_command(
    provider: str,
    model: str,
    api_key: str,
    context_dir: Path,
) -> list[str]:
    """Build the CLI command for the build step."""
    return [
        "uv",
        "run",
        "skene",
        "build",
        "--context",
        str(context_dir),
        "--provider",
        provider,
        "--model",
        model,
        "--api-key",
        api_key,
        "--target",
        "file",
        "--no-fallback",
        "--debug",
    ]


def _run_step(
    step_name: str,
    command: list[str],
    output_dir: Path,
    log_path: Path,
    timeout: int,
) -> StepMetadata:
    """Run a single CLI step, append output to log, return metadata."""
    logger.info(f"Running step: {step_name}")
    logger.debug(f"Command: {' '.join(command)}")

    start = time.monotonic()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.monotonic() - start

        # Append stdout/stderr to log file
        with open(log_path, "a") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"STEP: {step_name}\n")
            f.write(f"COMMAND: {' '.join(command)}\n")
            f.write(f"EXIT CODE: {result.returncode}\n")
            f.write(f"DURATION: {duration:.2f}s\n")
            f.write(f"{'=' * 60}\n")
            if result.stdout:
                f.write(f"\n--- STDOUT ---\n{result.stdout}\n")
            if result.stderr:
                f.write(f"\n--- STDERR ---\n{result.stderr}\n")

        success = result.returncode == 0
        if not success:
            logger.error(f"Step {step_name} failed with exit code {result.returncode}")
            if result.stderr:
                logger.error(f"stderr: {result.stderr[:500]}")

        return StepMetadata(
            step_name=step_name,
            exit_code=result.returncode,
            duration_seconds=round(duration, 2),
            command=command,
            success=success,
        )

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        logger.error(f"Step {step_name} timed out after {timeout}s")

        with open(log_path, "a") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"STEP: {step_name} — TIMED OUT after {timeout}s\n")
            f.write(f"{'=' * 60}\n")

        return StepMetadata(
            step_name=step_name,
            exit_code=-1,
            duration_seconds=round(duration, 2),
            command=command,
            success=False,
        )


def run_pipeline(
    codebase_path: Path,
    codebase_name: str,
    provider: str,
    model: str,
    model_name: str,
    api_key: str,
    output_dir: Path,
    run_number: int,
    timeout: int = 600,
) -> PipelineResult:
    """Run the full analyze -> plan -> build pipeline for one combo.

    Args:
        codebase_path: Path to the codebase to analyze.
        codebase_name: Display name for the codebase.
        provider: LLM provider name.
        model: LLM model identifier.
        model_name: Display name for the model.
        api_key: API key for the provider.
        output_dir: Directory to write output files to.
        run_number: Run number (for repeated runs).
        timeout: Timeout in seconds per step.

    Returns:
        PipelineResult with all step metadata and success status.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "cli-output.log"
    steps: list[StepMetadata] = []

    logger.info(f"Pipeline start: {codebase_name} / {model_name} / run-{run_number}")
    logger.info(f"Output dir: {output_dir}")

    # Step 1: Analyze
    analyze_cmd = _build_analyze_command(codebase_path, provider, model, api_key, output_dir)
    analyze_meta = _run_step("analyze", analyze_cmd, output_dir, log_path, timeout)
    steps.append(analyze_meta)

    if not analyze_meta.success:
        _write_metadata(output_dir, steps)
        return PipelineResult(
            codebase_name=codebase_name,
            model_name=model_name,
            provider=provider,
            model_id=model,
            run_number=run_number,
            output_dir=output_dir,
            steps=steps,
            success=False,
            error_message=f"analyze step failed (exit code {analyze_meta.exit_code})",
        )

    # Step 2: Plan
    plan_output = output_dir / "growth-plan.md"
    plan_cmd = _build_plan_command(provider, model, api_key, output_dir, plan_output)
    plan_meta = _run_step("plan", plan_cmd, output_dir, log_path, timeout)
    steps.append(plan_meta)

    if not plan_meta.success:
        _write_metadata(output_dir, steps)
        return PipelineResult(
            codebase_name=codebase_name,
            model_name=model_name,
            provider=provider,
            model_id=model,
            run_number=run_number,
            output_dir=output_dir,
            steps=steps,
            success=False,
            error_message=f"plan step failed (exit code {plan_meta.exit_code})",
        )

    # Step 3: Build
    build_cmd = _build_build_command(provider, model, api_key, output_dir)
    build_meta = _run_step("build", build_cmd, output_dir, log_path, timeout)
    steps.append(build_meta)

    _write_metadata(output_dir, steps)

    if not build_meta.success:
        return PipelineResult(
            codebase_name=codebase_name,
            model_name=model_name,
            provider=provider,
            model_id=model,
            run_number=run_number,
            output_dir=output_dir,
            steps=steps,
            success=False,
            error_message=f"build step failed (exit code {build_meta.exit_code})",
        )

    logger.info(f"Pipeline complete: {codebase_name} / {model_name} / run-{run_number}")
    return PipelineResult(
        codebase_name=codebase_name,
        model_name=model_name,
        provider=provider,
        model_id=model,
        run_number=run_number,
        output_dir=output_dir,
        steps=steps,
        success=True,
    )


def _redact_command(command: list[str]) -> list[str]:
    """Redact API keys from command arguments for safe storage."""
    redacted = []
    skip_next = False
    for i, arg in enumerate(command):
        if skip_next:
            redacted.append("***REDACTED***")
            skip_next = False
        elif arg == "--api-key" and i + 1 < len(command):
            redacted.append(arg)
            skip_next = True
        else:
            redacted.append(arg)
    return redacted


def _write_metadata(output_dir: Path, steps: list[StepMetadata]) -> None:
    """Write step metadata to metadata.json (with API keys redacted)."""
    safe_steps = []
    for step in steps:
        d = step.model_dump()
        d["command"] = _redact_command(d["command"])
        safe_steps.append(d)

    metadata = {
        "steps": safe_steps,
        "total_duration_seconds": round(sum(s.duration_seconds for s in steps), 2),
    }
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
