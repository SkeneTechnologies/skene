"""Tests for `skene attach` config persistence and the remote run client."""

from __future__ import annotations

import pytest

from skene.cli.commands.attach import _upsert_config_keys
from skene.cli.remote import RemoteServerError, _RunTracker


class TestUpsertConfigKeys:
    def test_adds_keys_to_missing_file(self, tmp_path):
        path = tmp_path / ".skene.config"
        _upsert_config_keys(path, {"server_url": "http://127.0.0.1:4906", "server_token": None})
        text = path.read_text()
        assert 'server_url = "http://127.0.0.1:4906"' in text
        assert "server_token" not in text

    def test_replaces_existing_and_preserves_others(self, tmp_path):
        path = tmp_path / ".skene.config"
        path.write_text('provider = "gemini"\nserver_url = "http://old:1"\n')
        _upsert_config_keys(path, {"server_url": "http://new:2"})
        text = path.read_text()
        assert 'provider = "gemini"' in text
        assert 'server_url = "http://new:2"' in text
        assert "http://old:1" not in text

    def test_none_removes_key(self, tmp_path):
        path = tmp_path / ".skene.config"
        path.write_text('server_url = "http://old:1"\nserver_token = "t"\nmodel = "m"\n')
        _upsert_config_keys(path, {"server_url": None, "server_token": None})
        text = path.read_text()
        assert "server_url" not in text and "server_token" not in text
        assert 'model = "m"' in text

    def test_result_is_valid_toml(self, tmp_path):
        from skene.config import load_toml

        path = tmp_path / ".skene.config"
        path.write_text('provider = "gemini"\n')
        _upsert_config_keys(path, {"server_url": "http://h:1", "server_token": "tok"})
        data = load_toml(path)
        assert data == {"provider": "gemini", "server_url": "http://h:1", "server_token": "tok"}


def _session_event(kind, sid, parent=None, agent="skene", error=None, title=None):
    properties = {"session": {"id": sid, "parentId": parent, "agent": agent, "title": title}}
    if error is not None:
        properties["error"] = error
    return {"type": kind, "properties": properties}


class TestRunTracker:
    def _tracker(self):
        tracker = _RunTracker()
        tracker.session_id = "ses_root"
        return tracker

    def test_root_idle_finishes(self):
        tracker = self._tracker()
        assert tracker.handle(_session_event("session.idle", "ses_root")) is True

    def test_child_lifecycle_and_features(self):
        tracker = self._tracker()
        assert tracker.handle(_session_event("session.created", "ses_child", parent="ses_root", agent="code")) is False
        assert tracker.handle(_session_event("session.idle", "ses_child")) is False
        part = {"type": "feature", "sessionId": "ses_child", "feature": {"proposedId": "user_signs_up"}}
        assert tracker.handle({"type": "part.created", "properties": {"part": part}}) is False
        assert tracker._features == 1

    def test_foreign_sessions_are_ignored(self):
        tracker = self._tracker()
        assert tracker.handle(_session_event("session.idle", "ses_other")) is False
        with pytest.raises(RemoteServerError):
            tracker.handle(_session_event("session.error", "ses_root", error="boom"))
        # An error in an unrelated tree does not raise.
        assert tracker.handle(_session_event("session.error", "ses_stranger", error="boom")) is False

    def test_child_error_raises(self):
        tracker = self._tracker()
        tracker.handle(_session_event("session.created", "ses_child", parent="ses_root", agent="code"))
        with pytest.raises(RemoteServerError, match="boom"):
            tracker.handle(_session_event("session.error", "ses_child", error="boom"))
