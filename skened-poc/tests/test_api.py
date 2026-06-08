from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from skened.api import create_app


def _wait_for_run(client: TestClient, run_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] in ("succeeded", "failed"):
            return run
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not finish in time")


def test_dashboard_served(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "SKENE" in r.text


def test_full_flow(git_repo: Path, settings):
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"

        # Register the project (auto-analyzes the default branch).
        r = client.post("/projects", json={"path": str(git_repo)})
        assert r.status_code == 201
        project = r.json()

        # Branches are listed live from git.
        branches = client.get(f"/projects/{project['id']}/branches").json()
        assert {b["name"] for b in branches} == {"main", "feature"}

        # The auto-enqueued default-branch run should complete.
        runs = client.get(f"/projects/{project['id']}/runs").json()
        assert len(runs) == 1
        run = _wait_for_run(client, runs[0]["id"])
        assert run["status"] == "succeeded"

        # The stored journey is retrievable and valid.
        journey = client.get(f"/projects/{project['id']}/branches/main/journey").json()
        assert journey["product"]["name"] == project["name"]
        assert journey["product"]["source_commit"] == run["commit"]

        # Analyze every branch.
        more = client.post(f"/projects/{project['id']}/analyze", json={"all": True}).json()
        assert {m["branch"] for m in more} == {"feature"}  # main already up to date
        _wait_for_run(client, more[0]["id"])

        # Unknown project -> 404.
        assert client.get("/projects/nope/branches").status_code == 404


def test_delete_project(git_repo: Path, settings):
    app = create_app(settings)
    with TestClient(app) as client:
        project = client.post("/projects", json={"path": str(git_repo)}).json()
        assert client.delete(f"/projects/{project['id']}").status_code == 204
        assert client.get(f"/projects/{project['id']}").status_code == 404


def test_gold_api_crud(git_repo: Path, settings):
    app = create_app(settings)
    with TestClient(app) as client:
        project = client.post("/projects", json={"path": str(git_repo)}).json()
        pid = project["id"]

        # No gold yet -> 404.
        assert client.get(f"/projects/{pid}/gold").status_code == 404

        # Build from the default branch.
        built = client.post(f"/projects/{pid}/gold/from-branch", json={}).json()
        assert built["product"]["name"] == project["name"]

        # Now retrievable.
        assert client.get(f"/projects/{pid}/gold").json()["product"]["name"] == project["name"]

        # Edit via PUT (full replacement) and read back.
        built["product"]["description"] = "edited via api"
        assert client.put(f"/projects/{pid}/gold", json=built).status_code == 200
        assert client.get(f"/projects/{pid}/gold").json()["product"]["description"] == "edited via api"

        # Delete.
        assert client.delete(f"/projects/{pid}/gold").status_code == 204
        assert client.get(f"/projects/{pid}/gold").status_code == 404
        assert client.delete(f"/projects/{pid}/gold").status_code == 404
