from __future__ import annotations

from fastapi.testclient import TestClient

from skened.api import create_app
from skened.config import Settings
from skened.service import DaemonService


def test_settings_get_and_patch_monitor(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        s = client.get("/settings").json()
        assert "monitor_enabled" in s and "monitor_on_commit" in s

        r = client.patch("/settings", json={"monitor_enabled": True, "monitor_on_commit": False})
        assert r.status_code == 200
        body = r.json()
        assert body["monitor_enabled"] is True
        assert body["monitor_on_commit"] is False


def test_settings_llm_backend_validation_and_key_masking(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        # backend=llm with no model → 400, state unchanged
        assert client.patch("/settings", json={"analysis_backend": "llm"}).status_code == 400
        assert client.get("/settings").json()["analysis_backend"] != "llm"

        # model + key → ok; key is stored but never returned
        r = client.patch("/settings", json={
            "analysis_backend": "llm", "llm_model": "gpt-4o", "llm_api_key": "sk-secret"})
        assert r.status_code == 200
        body = r.json()
        assert body["analysis_backend"] == "llm"
        assert body["llm_model"] == "gpt-4o"
        assert body["llm_api_key_set"] is True
        assert "llm_api_key" not in body
        assert "llm_api_key" not in client.get("/settings").json()

        # health reflects the live backend
        assert client.get("/health").json()["analysis"]["backend"] == "llm"


def test_settings_persist_across_restart(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        client.patch("/settings", json={"analysis_backend": "heuristic", "monitor_interval": 9.0})

    # A fresh service over the same data dir picks up the persisted overlay.
    fresh = Settings(data_dir=settings.data_dir)
    svc = DaemonService(fresh)
    try:
        assert svc.settings.monitor_interval == 9.0
        assert svc.settings.analysis_backend == "heuristic"
    finally:
        svc.db.close()
