"""Tests for resolve_cli_config base_url handling (skene provider)."""

import importlib

from skene.config import Config

_app = importlib.import_module("skene.cli.app")
resolve_cli_config = _app.resolve_cli_config


def test_skene_defaults_base_url_to_none_when_only_user_config(monkeypatch):
    """User-level base_url must not force localhost for skene when project omits base_url."""
    cfg = Config()
    cfg.set("provider", "skene")
    cfg.set("model", "auto")
    cfg.set("base_url", "http://localhost:3000")
    cfg.set("api_key", "sk-test")
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    monkeypatch.setattr(_app, "_project_config_defines_base_url", lambda: False)
    monkeypatch.delenv("SKENE_BASE_URL", raising=False)

    rc = resolve_cli_config()
    assert rc.provider == "skene"
    assert rc.base_url is None


def test_skene_uses_project_base_url(monkeypatch):
    cfg = Config()
    cfg.set("provider", "skene")
    cfg.set("base_url", "http://localhost:3000")
    cfg.set("api_key", "sk-test")
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    monkeypatch.setattr(_app, "_project_config_defines_base_url", lambda: True)
    monkeypatch.delenv("SKENE_BASE_URL", raising=False)

    rc = resolve_cli_config()
    assert rc.base_url == "http://localhost:3000"


def test_skene_cli_base_url_overrides(monkeypatch):
    cfg = Config()
    cfg.set("provider", "skene")
    cfg.set("base_url", "http://localhost:3000")
    cfg.set("api_key", "sk-test")
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    monkeypatch.setattr(_app, "_project_config_defines_base_url", lambda: True)
    monkeypatch.delenv("SKENE_BASE_URL", raising=False)

    rc = resolve_cli_config(base_url="https://www.skene.ai/api/v1")
    assert rc.base_url == "https://www.skene.ai/api/v1"


def test_skene_respects_skene_base_url_env(monkeypatch):
    cfg = Config()
    cfg.set("provider", "skene")
    cfg.set("base_url", "http://from-env")
    cfg.set("api_key", "sk-test")
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    monkeypatch.setattr(_app, "_project_config_defines_base_url", lambda: False)
    monkeypatch.setenv("SKENE_BASE_URL", "http://from-env")

    rc = resolve_cli_config()
    assert rc.base_url == "http://from-env"


def test_non_skene_still_uses_merged_base_url(monkeypatch):
    cfg = Config()
    cfg.set("provider", "openai")
    cfg.set("base_url", "https://example.com/v1")
    cfg.set("api_key", "x")
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    monkeypatch.delenv("SKENE_BASE_URL", raising=False)

    rc = resolve_cli_config()
    assert rc.base_url == "https://example.com/v1"
