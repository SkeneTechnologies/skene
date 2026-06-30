"""Gating tests for analyse-journey's first-run auto-publish.

`_maybe_auto_publish` must only push to Skene Cloud when: the TUI passed
``--auto-publish``, the run is on the skene provider with a linked workspace
(upstream URL + token), and skene.ai definitively reports no journey.yaml yet.
A True/None presence result (already published / indeterminate) must skip the
push, and a push failure must never raise.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from skene.cli.commands.analyse_journey import _maybe_auto_publish
from skene.config import Config


def _rc(provider="skene", upstream="https://skene.ai/workspace/w", token="sk_token"):
    cfg = Config()
    cfg.set("provider", provider)
    if upstream:
        cfg.set("upstream", upstream)
    if token:
        cfg.set("upstream_api_key", token)
    return SimpleNamespace(config=cfg)


def _jp(tmp_path):
    """The path analyse-journey would write the journey to."""
    return tmp_path / "skene-context" / "journey.yaml"


@pytest.fixture
def patched(monkeypatch):
    """Patch the lazily-imported collaborators and capture calls."""
    calls = {"exists": [], "publish": []}

    def fake_exists(api_base, tok):
        calls["exists"].append((api_base, tok))
        return calls["exists_result"]

    def fake_publish(project_root, config, **kwargs):
        calls["publish"].append((project_root, config, kwargs))
        return calls.get("publish_result", {"ok": True})

    monkeypatch.setattr("skene.growth_loops.upstream.journey_exists_upstream", fake_exists)
    monkeypatch.setattr("skene.growth_loops.push.publish_bundle", fake_publish)
    return calls


def test_disabled_does_nothing(patched, tmp_path):
    patched["exists_result"] = False
    _maybe_auto_publish(_rc(), tmp_path, journey_path=_jp(tmp_path), enabled=False)
    assert patched["exists"] == []
    assert patched["publish"] == []


def test_non_skene_provider_skips(patched, tmp_path):
    patched["exists_result"] = False
    _maybe_auto_publish(_rc(provider="openai"), tmp_path, journey_path=_jp(tmp_path), enabled=True)
    assert patched["exists"] == []
    assert patched["publish"] == []


def test_missing_upstream_skips(patched, tmp_path):
    patched["exists_result"] = False
    _maybe_auto_publish(_rc(upstream=""), tmp_path, journey_path=_jp(tmp_path), enabled=True)
    assert patched["exists"] == []
    assert patched["publish"] == []


def test_missing_token_skips(patched, tmp_path, monkeypatch):
    # Force token resolution to fail regardless of the host's env/credentials.
    monkeypatch.setattr("skene.config.resolve_upstream_token", lambda cfg: None)
    patched["exists_result"] = False
    _maybe_auto_publish(_rc(token=""), tmp_path, journey_path=_jp(tmp_path), enabled=True)
    assert patched["exists"] == []
    assert patched["publish"] == []


def test_already_published_skips(patched, tmp_path):
    patched["exists_result"] = True
    _maybe_auto_publish(_rc(), tmp_path, journey_path=_jp(tmp_path), enabled=True)
    assert len(patched["exists"]) == 1
    assert patched["publish"] == []


def test_indeterminate_skips(patched, tmp_path):
    patched["exists_result"] = None
    _maybe_auto_publish(_rc(), tmp_path, journey_path=_jp(tmp_path), enabled=True)
    assert len(patched["exists"]) == 1
    assert patched["publish"] == []


def test_absent_publishes(patched, tmp_path):
    patched["exists_result"] = False
    _maybe_auto_publish(_rc(), tmp_path, journey_path=_jp(tmp_path), enabled=True)
    assert len(patched["publish"]) == 1
    project_root, config, kwargs = patched["publish"][0]
    assert project_root == tmp_path
    assert kwargs["upstream"] == "https://skene.ai/workspace/w"
    assert kwargs["token"] == "sk_token"
    # The push is anchored to the journey's own directory, never config.output_dir
    # (which can resolve to a stale legacy skene/ bundle).
    assert kwargs["output_dir"] == str(_jp(tmp_path).parent)


def test_publish_failure_does_not_raise(patched, tmp_path):
    patched["exists_result"] = False

    def boom(*a, **k):
        raise RuntimeError("network down")

    with patch("skene.growth_loops.push.publish_bundle", boom):
        _maybe_auto_publish(_rc(), tmp_path, journey_path=_jp(tmp_path), enabled=True)  # must not raise
