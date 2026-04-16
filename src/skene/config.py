"""
Configuration file support for skene.

Supports loading config from:
1. Project-level: ./.skene.config
2. User-level: ~/.config/skene/config

Priority: CLI args > environment variables > project config > user config
"""

import os
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore

DEFAULT_MODEL_BY_PROVIDER = {
    "openai": "gpt-4o",
    "gemini": "gemini-3-flash-preview",  # v1beta API requires -preview suffix
    "anthropic": "claude-sonnet-4-5",
    "ollama": "llama3.3",
    "generic": "custom-model",
    "skene": "auto",
}


def default_model_for_provider(provider: str) -> str:
    """Return the default model for a given provider."""
    return DEFAULT_MODEL_BY_PROVIDER.get(provider.lower(), "gpt-4o-mini")


class Config:
    """Configuration container with hierarchical loading."""

    def __init__(self):
        self._values: dict[str, Any] = {}
        self._base_url_from_skene_env = False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value."""
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value."""
        self._values[key] = value

    def update(self, values: dict[str, Any]) -> None:
        """Update config with new values (existing values take precedence)."""
        for key, value in values.items():
            if key not in self._values:
                self._values[key] = value

    @property
    def api_key(self) -> str | None:
        """Get API key."""
        key = self.get("api_key")
        # Treat empty strings as None
        return key if key else None

    @property
    def provider(self) -> str:
        """Get LLM provider."""
        return self.get("provider", "openai")

    @property
    def output_dir(self) -> str:
        """Get default output directory."""
        return self.get("output_dir", "./skene-context")

    @property
    def verbose(self) -> bool:
        """Get verbose flag."""
        return self.get("verbose", False)

    @property
    def debug(self) -> bool:
        """Get debug flag for LLM input/output logging."""
        return self.get("debug", False)

    @property
    def model(self) -> str:
        """Get LLM model name."""
        model = self.get("model")
        if model:
            return model
        return default_model_for_provider(self.provider)

    @property
    def exclude_folders(self) -> list[str]:
        """Get list of folder names to exclude from analysis."""
        exclude = self.get("exclude_folders")
        if exclude:
            if isinstance(exclude, list):
                return exclude
            elif isinstance(exclude, str):
                return [exclude]
        return []

    @property
    def base_url(self) -> str | None:
        """Get base URL for OpenAI-compatible providers."""
        return self.get("base_url")

    @property
    def base_url_from_skene_env(self) -> bool:
        """Return True when SKENE_BASE_URL populated this config."""
        return self._base_url_from_skene_env

    @property
    def upstream(self) -> str | None:
        """Get upstream URL for push (e.g. https://skene.ai/workspace/my-app)."""
        url = self.get("upstream") or self.get("upstream_url")
        return url.strip() if isinstance(url, str) and url.strip() else None

    @property
    def upstream_api_key(self) -> str | None:
        """Get upstream API key. Precedence: SKENE_UPSTREAM_API_KEY env > config > credentials file."""
        return self.get("upstream_api_key")


def find_project_config() -> Path | None:
    """Find project-level config file (.skene.config)."""
    cwd = Path.cwd()

    # Search up the directory tree
    for parent in [cwd, *cwd.parents]:
        config_path = parent / ".skene.config"
        if config_path.exists():
            return config_path

    return None


def save_upstream_to_config(upstream_url: str, workspace_slug: str, api_key: str) -> Path:
    """Save upstream connection info and API key to .skene.config.

    Creates the file if it doesn't exist, or merges into the existing one
    preserving all other settings.
    """
    config_path = find_project_config() or (Path.cwd() / ".skene.config")

    existing: dict[str, Any] = {}
    if config_path.exists():
        try:
            existing = load_toml(config_path)
        except Exception:
            pass

    existing["upstream"] = upstream_url
    existing["workspace"] = workspace_slug
    existing["upstream_api_key"] = api_key

    _write_config_toml(config_path, existing)
    return config_path


def remove_upstream_from_config() -> Path | None:
    """Remove upstream, workspace, and upstream_api_key from .skene.config.

    Returns path if the file was found and updated, None otherwise.
    """
    config_path = find_project_config()
    if not config_path or not config_path.exists():
        return None

    try:
        existing = load_toml(config_path)
    except Exception:
        return None

    changed = False
    for key in ("upstream", "upstream_url", "workspace", "upstream_api_key"):
        if key in existing:
            del existing[key]
            changed = True

    if not changed:
        return None

    _write_config_toml(config_path, existing)
    return config_path


def _write_config_toml(path: Path, data: dict[str, Any]) -> None:
    """Write a flat dict as a TOML file, preserving all keys."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        elif isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, list):
            items = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in value)
            lines.append(f"{key} = [{items}]")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        else:
            lines.append(f'{key} = "{value}"')
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    if sys.platform != "win32":
        try:
            path.chmod(0o600)
        except (OSError, PermissionError):
            pass


def find_user_config() -> Path | None:
    """Find user-level config file (~/.config/skene/config)."""
    # XDG_CONFIG_HOME or ~/.config
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        config_dir = Path(config_home) / "skene"
    else:
        config_dir = Path.home() / ".config" / "skene"

    config_path = config_dir / "config"
    if config_path.exists():
        return config_path

    return None


def resolve_upstream_token(config: Config) -> str | None:
    """Resolve upstream API key. See resolve_upstream_api_key_with_source for precedence."""
    key, _ = resolve_upstream_api_key_with_source(config)
    return key


def resolve_upstream_api_key_with_source(config: Config) -> tuple[str | None, str]:
    """
    Resolve upstream API key and its source. Returns (api_key, source).

    Precedence:
    1. SKENE_UPSTREAM_API_KEY env
    2. upstream_api_key from .skene.config (or user config)
    """
    env_key = os.environ.get("SKENE_UPSTREAM_API_KEY")
    if env_key:
        return env_key.strip(), "env"

    if config.upstream_api_key:
        return config.upstream_api_key.strip(), "config"

    return None, "-"


def load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config() -> Config:
    """
    Load configuration with proper precedence.

    Priority (highest to lowest):
    1. CLI arguments (applied later by CLI)
    2. Environment variables
    3. Project-level config (./.skene.config)
    4. User-level config (~/.config/skene/config)
    """
    config = Config()

    # Start with user config (lowest priority)
    user_config = find_user_config()
    if user_config:
        try:
            data = load_toml(user_config)
            config.update(data)
        except Exception:
            pass  # Ignore malformed config

    # Apply project config (higher priority)
    project_config = find_project_config()
    if project_config:
        try:
            data = load_toml(project_config)
            # Project config overwrites user config
            for key, value in data.items():
                config.set(key, value)
        except Exception:
            pass  # Ignore malformed config

    # Apply environment variables (highest priority before CLI)
    if api_key := os.environ.get("SKENE_API_KEY"):
        config.set("api_key", api_key)
    if provider := os.environ.get("SKENE_PROVIDER"):
        config.set("provider", provider)
    if base_url := os.environ.get("SKENE_BASE_URL"):
        config.set("base_url", base_url)
        config._base_url_from_skene_env = True
    if os.environ.get("SKENE_DEBUG", "").lower() in ("1", "true", "yes"):
        config.set("debug", True)
    if api_key := os.environ.get("SKENE_UPSTREAM_API_KEY"):
        config.set("upstream_api_key", api_key.strip() if api_key else None)

    return config
