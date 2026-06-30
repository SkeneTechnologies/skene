"""Tests that the provider API key is stored in the keyring, not in clear text."""

from __future__ import annotations

from pathlib import Path

import pytest

from skene import config as config_module
from skene import secret_store
from skene.cli import config_manager


@pytest.fixture
def fake_keyring(monkeypatch):
    """Replace the OS keyring with an in-memory store for the duration of a test."""
    store: dict[tuple[str, str], str] = {}

    def fake_set(api_key: str) -> bool:
        store[(secret_store.KEYRING_SERVICE, secret_store.API_KEY_ACCOUNT)] = api_key
        return True

    def fake_get() -> str | None:
        return store.get((secret_store.KEYRING_SERVICE, secret_store.API_KEY_ACCOUNT))

    def fake_delete() -> bool:
        return store.pop((secret_store.KEYRING_SERVICE, secret_store.API_KEY_ACCOUNT), None) is not None

    monkeypatch.setattr(secret_store, "set_api_key", fake_set)
    monkeypatch.setattr(secret_store, "get_api_key", fake_get)
    monkeypatch.setattr(secret_store, "delete_api_key", fake_delete)
    return store


def test_save_config_does_not_write_api_key_to_file(fake_keyring, tmp_path):
    """The API key must never appear in the config file on disk (CWE-312)."""
    config_path = tmp_path / "config"
    save_key = "sk-super-secret-value"

    config_manager.save_config(config_path, "openai", "gpt-4o", save_key)

    contents = config_path.read_text()
    assert save_key not in contents
    assert "api_key" not in contents
    # The secret lives in the (faked) keyring instead.
    assert fake_keyring[(secret_store.KEYRING_SERVICE, secret_store.API_KEY_ACCOUNT)] == save_key


def test_load_config_reads_api_key_from_keyring(fake_keyring, monkeypatch, tmp_path):
    """load_config falls back to the keyring when no env/file key is present."""
    monkeypatch.setattr(config_module, "find_user_config", lambda: None)
    monkeypatch.setattr(config_module, "find_project_config", lambda: None)
    monkeypatch.delenv("SKENE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    secret_store.set_api_key("sk-from-keyring")
    cfg = config_module.load_config()

    assert cfg.api_key == "sk-from-keyring"


def test_save_then_load_round_trip(fake_keyring, monkeypatch, tmp_path):
    """A key saved via save_config is read back by load_config."""
    monkeypatch.setattr(config_module, "find_user_config", lambda: None)
    monkeypatch.setattr(config_module, "find_project_config", lambda: None)
    monkeypatch.delenv("SKENE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config"
    config_manager.save_config(config_path, "anthropic", "claude-sonnet-4-5", "sk-roundtrip")

    monkeypatch.setattr(config_module, "find_user_config", lambda: Path(config_path))
    cfg = config_module.load_config()

    assert cfg.api_key == "sk-roundtrip"
    assert cfg.provider == "anthropic"


def test_env_var_takes_precedence_over_keyring(fake_keyring, monkeypatch, tmp_path):
    """SKENE_API_KEY overrides whatever is stored in the keyring."""
    monkeypatch.setattr(config_module, "find_user_config", lambda: None)
    monkeypatch.setattr(config_module, "find_project_config", lambda: None)
    monkeypatch.chdir(tmp_path)

    secret_store.set_api_key("sk-keyring")
    monkeypatch.setenv("SKENE_API_KEY", "sk-env")
    cfg = config_module.load_config()

    assert cfg.api_key == "sk-env"


def test_empty_key_deletes_stored_secret(fake_keyring, tmp_path):
    """Saving an empty key clears any previously stored secret."""
    secret_store.set_api_key("sk-old")
    config_path = tmp_path / "config"

    config_manager.save_config(config_path, "openai", "gpt-4o", "")

    assert secret_store.get_api_key() is None
