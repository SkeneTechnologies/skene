"""
CLI app definition and shared helpers for skene.

This module creates the Typer app, defines the shared config resolution
helper (ResolvedConfig), and registers all command modules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import click
import typer
from typer.core import TyperGroup

from skene import __version__
from skene.config import Config, default_model_for_provider, find_project_config, load_config, load_toml
from skene.output import apply_verbosity, console, error

# ---------------------------------------------------------------------------
# Command ordering for --help
# ---------------------------------------------------------------------------

_COMMAND_ORDER = [
    "analyze",
    "plan",
    "build",
    "status",
    "push",
    "config",
    "validate",
    "login",
    "logout",
    "features",
]


class SectionedHelpGroup(TyperGroup):
    """TyperGroup that lists commands in a specific order for help output."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        ordered = [c for c in _COMMAND_ORDER if c in self.commands]
        extra = [c for c in self.commands if c not in _COMMAND_ORDER]
        return ordered + extra


app = typer.Typer(
    name="skene",
    help="PLG analysis toolkit for codebases. Analyze code, detect growth opportunities.",
    add_completion=False,
    no_args_is_help=True,
    cls=SectionedHelpGroup,
)

# ---------------------------------------------------------------------------
# Provider constants and helpers
# ---------------------------------------------------------------------------

_OPENAI_COMPAT_PROVIDERS = ("generic", "openai-compatible", "openai_compatible")
_LOCAL_NO_KEY_PROVIDERS = (
    "lmstudio",
    "lm-studio",
    "lm_studio",
    "ollama",
    *_OPENAI_COMPAT_PROVIDERS,
)

# Default upstream ingest URL when --local is used without --ingest-url
DEFAULT_LOCAL_INGEST_BASE = "https://www.skene.ai"


def is_local_provider(provider: str) -> bool:
    """Return True for providers that can run without a real API key."""
    return provider.lower() in _LOCAL_NO_KEY_PROVIDERS


def requires_base_url(provider: str) -> bool:
    """Return True when provider requires --base-url."""
    return provider.lower() in _OPENAI_COMPAT_PROVIDERS


def _project_config_defines_base_url() -> bool:
    """True when project .skene.config contains a non-empty base_url key."""
    path = find_project_config()
    if path is None or not path.exists():
        return False
    try:
        data = load_toml(path)
    except Exception:
        return False
    value = data.get("base_url")
    return isinstance(value, str) and bool(value.strip())


def _resolve_base_url(
    *,
    provider: str,
    cli_base_url: str | None,
    merged_config_base_url: str | None,
) -> str | None:
    """
    Resolve LLM base URL.

    For provider ``skene``, default to Skene Cloud API (via ``None`` → SkeneClient
    production endpoint) unless ``base_url`` is set via CLI, ``SKENE_BASE_URL``,
    or project ``.skene.config``. User-level config alone does not pin base_url
    for skene, so a stale global ``localhost`` does not override production.
    """
    p = (provider or "").lower()
    cli = (cli_base_url or "").strip() if cli_base_url is not None else ""
    if cli:
        return cli

    if p == "skene":
        if os.environ.get("SKENE_BASE_URL", "").strip():
            return merged_config_base_url
        if _project_config_defines_base_url():
            return merged_config_base_url
        return None

    return merged_config_base_url


# ---------------------------------------------------------------------------
# Shared config resolution
# ---------------------------------------------------------------------------


@dataclass
class ResolvedConfig:
    """CLI flags merged with config-file defaults."""

    api_key: str | None
    provider: str
    model: str
    base_url: str | None
    debug: bool
    is_local: bool
    config: Config  # raw config for command-specific fields


def resolve_cli_config(
    *,
    api_key: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    quiet: bool = False,
    debug: bool = False,
) -> ResolvedConfig:
    """Merge CLI flags with config file defaults, set verbosity, validate provider constraints.

    Call once at the start of each command.  Raises ``typer.Exit(1)`` if the
    generic provider is selected without ``--base-url``.
    """
    config = load_config()
    resolved_debug = apply_verbosity(quiet, debug, config.debug)
    resolved_provider = provider or config.provider
    resolved_base_url = _resolve_base_url(
        provider=resolved_provider,
        cli_base_url=base_url,
        merged_config_base_url=config.base_url,
    )
    resolved_model = model or config.get("model") or default_model_for_provider(resolved_provider)
    resolved_api_key = api_key or config.api_key
    is_local = is_local_provider(resolved_provider)

    if requires_base_url(resolved_provider) and not resolved_base_url:
        error(f"The '{resolved_provider}' provider requires --base-url to be set.")
        raise typer.Exit(1)

    return ResolvedConfig(
        api_key=resolved_api_key,
        provider=resolved_provider,
        model=resolved_model,
        base_url=resolved_base_url,
        debug=resolved_debug,
        is_local=is_local,
        config=config,
    )


# ---------------------------------------------------------------------------
# Version callback and app-level options
# ---------------------------------------------------------------------------


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"[bold]skene[/bold] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
):
    """
    skene - PLG analysis toolkit for codebases.

    Analyze your codebase, detect growth opportunities, and generate documentation.

    Workflow suggestion:
        analyze -> plan

    Quick start with uvx (no installation required):

        uvx skene analyze .
        # Or: uvx skene analyze .

    Or install with pip:

        pip install skene
        skene analyze .
        # Or: skene analyze .
    """
    pass


# ---------------------------------------------------------------------------
# Sub-app registration
# ---------------------------------------------------------------------------

from skene.cli.features import features_app  # noqa: E402

app.add_typer(features_app, name="features", rich_help_panel="manage")

# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _run_cli(app_fn) -> None:
    """Run CLI app."""
    app_fn()


def skene_entry_point():
    """Entry point for 'skene' command."""
    _run_cli(app)


def skene_growth_entry():
    """Entry point for 'skene-growth' command (development). Use 'skene' for production."""
    _run_cli(app)


# ---------------------------------------------------------------------------
# Command registration — import command modules so their @app.command()
# decorators run.  Must be AFTER app is defined to avoid circular imports.
# ---------------------------------------------------------------------------

from skene.cli.commands import (  # noqa: E402, F401
    analyze,
    build,
    config_cmd,
    login,
    plan,
    push,
    status_cmd,
    validate,
)
