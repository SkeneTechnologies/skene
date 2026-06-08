"""Runtime configuration and data-directory layout.

All daemon state lives under a single data dir (``~/.skene`` by default). Settings
can be overridden via ``SKENE_*`` environment variables, which is also how tests point
the daemon at a throwaway directory.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AnalysisBackend = Literal["auto", "heuristic", "llm"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SKENE_", env_file=".env", extra="ignore")

    data_dir: Path = Path.home() / ".skene"
    host: str = "127.0.0.1"
    port: int = 8787
    worker_concurrency: int = 2

    # Working-branch monitor: auto-analyze the checked-out branch when it changes.
    monitor_enabled: bool = True
    monitor_interval: float = 3.0
    monitor_on_commit: bool = True  # if False, fire only on branch switch, not on new commits

    # --- analysis backend ----------------------------------------------------
    # "auto": use the LLM when ``llm_model`` is set, else heuristics.
    # "llm": require an LLM (errors if ``llm_model`` is unset).
    # "heuristic": always use the offline rule-based pipeline.
    analysis_backend: AnalysisBackend = "auto"

    # LiteLLM model string, e.g. "anthropic/claude-sonnet-4-6", "gpt-4o", "ollama/llama3".
    llm_model: str | None = None
    # Optional explicit key/endpoint. LiteLLM also reads provider env vars
    # (OPENAI_API_KEY, ANTHROPIC_API_KEY, ...) automatically when these are unset.
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_temperature: float = 0.0
    llm_max_turns: int = 40          # agent-loop cap for the code agent
    llm_classify_concurrency: int = 8

    @property
    def llm_enabled(self) -> bool:
        if self.analysis_backend == "heuristic":
            return False
        if self.analysis_backend == "llm":
            return True
        return bool(self.llm_model)  # "auto"

    # --- derived paths -------------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.data_dir / "skene.db"

    @property
    def worktrees_dir(self) -> Path:
        return self.data_dir / "worktrees"

    @property
    def journeys_dir(self) -> Path:
        return self.data_dir / "journeys"

    @property
    def gold_dir(self) -> Path:
        return self.data_dir / "gold"

    @property
    def pid_file(self) -> Path:
        return self.data_dir / "daemon.pid"

    @property
    def log_file(self) -> Path:
        return self.data_dir / "daemon.log"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.worktrees_dir, self.journeys_dir, self.gold_dir):
            d.mkdir(parents=True, exist_ok=True)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton (cache cleared by tests via ``get_settings.cache_clear``)."""
    return Settings()
