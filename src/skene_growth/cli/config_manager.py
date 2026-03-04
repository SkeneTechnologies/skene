"""Configuration management utilities for CLI."""

import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()


def _set_config_permissions(config_path: Path) -> None:
    """Set restrictive permissions on config file (owner read/write only).

    On Unix-like systems, sets permissions to 0o600.
    On Windows, this is a no-op as Windows handles file permissions differently.
    """
    if sys.platform != "win32":
        try:
            config_path.chmod(0o600)
        except (OSError, PermissionError):
            pass


def get_provider_models(provider: str) -> list[str]:
    """Get list of recommended models for a provider (up to 5)."""
    models_by_provider = {
        "openai": [
            "gpt-5.2",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
        ],
        "gemini": [
            "gemini-3-flash-preview",  # v1beta API (Speed/Value - Daily Driver)
            "gemini-3-pro-preview",  # v1beta API (Flagship - King of Versatility)
            "gemini-2.5-flash",  # Legacy/Stable
            "gemini-2.5-pro",  # Legacy/Stable
            "gemini-3-nano-preview",  # Legacy
        ],
        "anthropic": [
            "claude-opus-4-5",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
        ],
        "lmstudio": [
            "custom-model",
            "llama-3.3-70b",
            "llama-3.3-8b",
            "mistral-large",
            "phi-4",
        ],
        "lm-studio": [
            "custom-model",
            "llama-3.3-70b",
            "llama-3.3-8b",
            "mistral-large",
            "phi-4",
        ],
        "lm_studio": [
            "custom-model",
            "llama-3.3-70b",
            "llama-3.3-8b",
            "mistral-large",
            "phi-4",
        ],
        "ollama": [
            "llama3.3",
            "llama3.2",
            "mistral",
            "qwen2.5",
            "phi4",
        ],
        "generic": [
            "custom-model",
        ],
    }
    return models_by_provider.get(provider.lower(), ["gpt-4o"])


def save_config(config_path: Path, provider: str, model: str, api_key: str, base_url: str | None = None) -> None:
    """Save configuration to a TOML file."""
    from skene_growth.config import load_toml

    # Read existing config if it exists
    existing_config = {}
    if config_path.exists():
        try:
            existing_config = load_toml(config_path)
        except Exception:
            pass  # If we can't read it, start fresh

    # Write TOML file manually
    config_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# skene-growth configuration"]
    lines.append("# See: https://github.com/skene-technologies/skene-growth")
    lines.append("")
    lines.append("# API key for LLM provider (can also use SKENE_API_KEY env var)")
    lines.append(f'api_key = "{api_key}"')
    lines.append("")
    lines.append("# LLM provider to use")
    lines.append(f'provider = "{provider}"')
    lines.append("")
    lines.append("# Model to use")
    lines.append(f'model = "{model}"')
    lines.append("")

    if base_url:
        lines.append("# Base URL for OpenAI-compatible provider")
        lines.append(f'base_url = "{base_url}"')
        lines.append("")

    # Preserve other settings (including upstream, upstream_token)
    for key, value in existing_config.items():
        if key not in ["api_key", "provider", "model", "base_url"]:
            if isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            elif isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, list):
                lines.append(f"{key} = {value}")
            else:
                lines.append(f"{key} = {value}")

    # Add defaults if not present
    if "output_dir" not in existing_config:
        lines.append("")
        lines.append("# Default output directory")
        lines.append('output_dir = "./skene-context"')

    if "verbose" not in existing_config:
        lines.append("")
        lines.append("# Enable verbose output")
        lines.append("verbose = false")

    config_path.write_text("\n".join(lines))
    _set_config_permissions(config_path)


def interactive_config_setup() -> tuple[Path, str, str, str, str | None]:
    """
    Interactive configuration setup.

    Returns:
        Tuple of (config_path, provider, model, api_key, base_url)
    """
    from skene_growth.config import find_project_config, find_user_config, load_config

    # Load current config
    cfg = load_config()
    project_cfg = find_project_config()
    user_cfg = find_user_config()

    # Determine which config file to edit (prefer project, fallback to user)
    config_path = project_cfg if project_cfg else user_cfg
    if not config_path:
        # Create user config if neither exists
        config_home = os.environ.get("XDG_CONFIG_HOME")
        if config_home:
            config_dir = Path(config_home) / "skene-growth"
        else:
            config_dir = Path.home() / ".config" / "skene-growth"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config"

    current_provider = cfg.provider
    current_model = cfg.model
    api_key = cfg.api_key

    # Ask for provider
    console.print()
    providers = [
        ("openai", "OpenAI"),
        ("gemini", "Google Gemini"),
        ("anthropic", "Anthropic"),
        ("lmstudio", "LM Studio"),
        ("ollama", "Ollama"),
        ("generic", "OpenAI compatible API"),
    ]
    provider_options = "\n".join([f"  {i + 1}. {label}" for i, (_key, label) in enumerate(providers)])
    console.print(f"[bold]Select LLM provider:[/bold]\n{provider_options}")

    provider_keys = [key for key, _label in providers]

    while True:
        provider_choice = Prompt.ask(
            f"\n[cyan]Provider[/cyan] (1-{len(providers)})",
            default=str(provider_keys.index(current_provider) + 1) if current_provider in provider_keys else "1",
        )
        try:
            idx = int(provider_choice) - 1
            if 0 <= idx < len(providers):
                selected_provider = providers[idx][0]
                break
            else:
                console.print(
                    "[red]Invalid choice. Please enter a number between 1 and {}[/red]".format(len(providers))
                )
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")

    # Ask for model based on provider
    console.print()
    models = get_provider_models(selected_provider)
    model_options = "\n".join([f"  {i + 1}. {m}" for i, m in enumerate(models)])
    console.print(f"[bold]Select model:[/bold]\n{model_options}")

    # Determine default model
    default_model_idx = None
    default_model_text = ""

    if selected_provider == current_provider and current_model in models:
        default_model_idx = str(models.index(current_model) + 1)
        default_model_text = f" (current: {current_model})"
    elif selected_provider == current_provider and current_model:
        console.print(
            f"\n[dim]Note: Current model '{current_model}' not in recommended list. You can enter it manually.[/dim]"
        )

    while True:
        prompt_text = f"\n[cyan]Model[/cyan] (1-{len(models)} or enter custom model name)"
        if default_model_text:
            prompt_text += default_model_text

        model_choice = Prompt.ask(prompt_text, default=default_model_idx if default_model_idx else "1")

        try:
            idx = int(model_choice) - 1
            if 0 <= idx < len(models):
                selected_model = models[idx]
                break
            else:
                console.print("[yellow]Number out of range. Using as custom model name.[/yellow]")
                selected_model = model_choice
                break
        except ValueError:
            # Allow custom model name
            selected_model = model_choice
            break

    # Ask for base URL if generic provider
    base_url = None
    if selected_provider == "generic":
        console.print()
        while True:
            base_url = Prompt.ask("[cyan]Base URL[/cyan] (e.g. https://your-service.com/v1)")
            if base_url:
                break
            console.print("[red]Base URL is required for the generic provider.[/red]")

    # Ask for API key
    console.print()
    api_key_prompt = "[cyan]API Key[/cyan]"
    if api_key:
        api_key_prompt += f" (current: {api_key[:4]}...{api_key[-4:]}, press Enter to keep)"
    api_key_prompt += ": "

    new_api_key = Prompt.ask(api_key_prompt, password=True, default="")

    # If user pressed Enter without typing, keep existing API key
    if not new_api_key and api_key:
        new_api_key = api_key
    elif not new_api_key:
        console.print("[yellow]No API key provided. Configuration will be saved without API key.[/yellow]")
        new_api_key = ""

    return config_path, selected_provider, selected_model, new_api_key, base_url


def show_config_status(cfg, project_cfg, user_cfg):
    """Display current configuration status."""
    from skene_growth.config import resolve_upstream_token

    console.print(Panel.fit("[bold blue]Configuration[/bold blue]", title="skene-growth"))

    table = Table(title="Config Files")
    table.add_column("Type", style="cyan")
    table.add_column("Path", style="white")
    table.add_column("Status", style="green")

    table.add_row(
        "Project",
        str(project_cfg) if project_cfg else "./.skene-growth.config",
        "[green]Found[/green]" if project_cfg else "[dim]Not found[/dim]",
    )
    table.add_row(
        "User",
        str(user_cfg) if user_cfg else "~/.config/skene-growth/config",
        "[green]Found[/green]" if user_cfg else "[dim]Not found[/dim]",
    )
    console.print(table)

    console.print()

    values_table = Table(title="Current Values")
    values_table.add_column("Setting", style="cyan")
    values_table.add_column("Value", style="white")
    values_table.add_column("Source", style="dim")

    # Show API key (masked)
    api_key = cfg.api_key
    if api_key:
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
        values_table.add_row("api_key", masked, "config/env")
    else:
        values_table.add_row("api_key", "[dim]Not set[/dim]", "-")

    current_provider = cfg.provider
    current_model = cfg.model

    values_table.add_row("provider", current_provider, "config/default")
    values_table.add_row("model", current_model, "config/default")
    values_table.add_row("output_dir", cfg.output_dir, "config/default")
    values_table.add_row("verbose", str(cfg.verbose), "config/default")

    from skene_growth.config import load_project_upstream

    project = load_project_upstream()
    upstream_val = (project.get("upstream") if project else None) or cfg.upstream or "[dim]Not set[/dim]"
    source = ".skene-upstream" if (project and project.get("upstream")) else "config/env"
    values_table.add_row("upstream", upstream_val, source)
    token = resolve_upstream_token(cfg)
    if token:
        masked = token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
        values_table.add_row("upstream_token", masked, "credentials")
    else:
        values_table.add_row("upstream_token", "[dim]Not set[/dim]", "-")

    console.print(values_table)


def create_sample_config(config_path: Path) -> None:
    """Create a sample configuration file."""
    sample_config = """# skene-growth configuration
# See: https://github.com/skene-technologies/skene-growth

# API key for LLM provider (can also use SKENE_API_KEY env var)
# api_key = "your-gemini-api-key"

# LLM provider to use (default: gemini)
provider = "gemini"

# Default output directory
output_dir = "./skene-context"

# Enable verbose output
verbose = false
"""
    config_path.write_text(sample_config)
    _set_config_permissions(config_path)
