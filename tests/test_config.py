"""Tests for environment-variable overrides in skene.config.load_config."""

from __future__ import annotations

import pytest

from skene import config as config_module
from skene.output_paths import DEFAULT_OUTPUT_DIR


@pytest.fixture
def no_config_files(monkeypatch, tmp_path):
    """Isolate load_config from user/project config files on disk."""
    monkeypatch.setattr(config_module, "find_user_config", lambda: None)
    monkeypatch.setattr(config_module, "find_project_config", lambda: None)
    monkeypatch.chdir(tmp_path)


def test_skene_output_dir_env_overrides_default(monkeypatch, no_config_files):
    """SKENE_OUTPUT_DIR env var is applied to config after file-based loading."""
    monkeypatch.setenv("SKENE_OUTPUT_DIR", "./my-custom-dir")
    cfg = config_module.load_config()
    assert cfg.output_dir == "./my-custom-dir"


def test_skene_output_dir_absent_falls_back(monkeypatch, no_config_files):
    """Without SKENE_OUTPUT_DIR and no config files, the default is used."""
    monkeypatch.delenv("SKENE_OUTPUT_DIR", raising=False)
    cfg = config_module.load_config()
    assert cfg.output_dir == DEFAULT_OUTPUT_DIR
