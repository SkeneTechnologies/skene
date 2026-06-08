"""``skene`` CLI. Talks to the running daemon over HTTP so the daemon stays the single
source of truth; only ``up``/``down`` manage the process directly.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import typer

from .config import get_settings

app = typer.Typer(help="Skene daemon control CLI", no_args_is_help=True)
project_app = typer.Typer(help="Manage projects", no_args_is_help=True)
gold_app = typer.Typer(help="Manage the gold standard (gap-analysis target)", no_args_is_help=True)
app.add_typer(project_app, name="project")
app.add_typer(gold_app, name="gold")


def _client() -> httpx.Client:
    return httpx.Client(base_url=get_settings().base_url, timeout=30.0)


def _check(resp: httpx.Response) -> httpx.Response:
    if resp.status_code >= 400:
        detail = resp.json().get("detail") if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        typer.secho(f"error {resp.status_code}: {detail}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    return resp


def _require_daemon() -> httpx.Client:
    client = _client()
    try:
        client.get("/health")
    except httpx.ConnectError:
        typer.secho("daemon is not running — start it with `skene up`", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    return client


# --- lifecycle -----------------------------------------------------------------
@app.command()
def up(detach: bool = typer.Option(False, "--detach", "-d", help="Run in the background")):
    """Start the daemon."""
    settings = get_settings()
    settings.ensure_dirs()

    # Already up?
    try:
        _client().get("/health")
        typer.echo(f"daemon already running at {settings.base_url}")
        return
    except httpx.ConnectError:
        pass

    if not detach:
        from .__main__ import main as run_server

        typer.echo(f"starting daemon at {settings.base_url} — dashboard at {settings.base_url} (Ctrl-C to stop)")
        run_server()
        return

    log = open(settings.log_file, "ab")  # noqa: SIM115 — handed to the child process
    proc = subprocess.Popen(
        [sys.executable, "-m", "skened"],
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    settings.pid_file.write_text(str(proc.pid))

    # Wait briefly for readiness.
    for _ in range(50):
        try:
            _client().get("/health")
            typer.echo(f"daemon started (pid {proc.pid}) — open {settings.base_url} for the dashboard")
            return
        except httpx.ConnectError:
            time.sleep(0.1)
    typer.secho(f"daemon process started (pid {proc.pid}) but not responding yet; check {settings.log_file}", fg=typer.colors.YELLOW)


@app.command()
def down():
    """Stop the daemon."""
    settings = get_settings()
    if not settings.pid_file.exists():
        typer.echo("no pid file; daemon not started via `skene up --detach`")
        raise typer.Exit(0)
    pid = int(settings.pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        typer.echo(f"sent SIGTERM to daemon (pid {pid})")
    except ProcessLookupError:
        typer.echo(f"daemon (pid {pid}) not running")
    finally:
        settings.pid_file.unlink(missing_ok=True)


@app.command()
def config():
    """Show the daemon's effective analysis configuration (backend, model)."""
    client = _require_daemon()
    health = client.get("/health").json()
    info = health.get("analysis", {})
    mon = health.get("monitor", {})
    s = get_settings()
    typer.secho(f"endpoint:    {s.base_url}", fg=typer.colors.GREEN)
    typer.echo(f"data dir:    {s.data_dir}")
    _trig = "switch+commit" if mon.get("on_commit") else "switch only"
    typer.echo(f"monitor:     {'on' if mon.get('enabled') else 'off'} (every {mon.get('interval')}s, {_trig})")
    typer.echo(f"backend:     {info.get('backend')}  (llm_enabled={info.get('llm_enabled')})")
    typer.echo(f"model:       {info.get('model') or '(none)'}")
    typer.echo(f"extractor:   {info.get('extractor')}")
    typer.echo(f"classifier:  {info.get('classifier')}")
    typer.echo(f"brancher:    {info.get('brancher') or '(deterministic diff)'}")
    if not info.get("llm_enabled"):
        typer.echo("")
        typer.secho("To enable LLMs: uv sync --extra llm, then set e.g.", fg=typer.colors.YELLOW)
        typer.echo("  export SKENE_LLM_MODEL=anthropic/claude-sonnet-4-6")
        typer.echo("  export ANTHROPIC_API_KEY=...   (or SKENE_LLM_API_KEY=...)")
        typer.echo("  then restart the daemon (skene down && skene up --detach)")


@app.command()
def status():
    """Show daemon health and registered projects."""
    client = _require_daemon()
    health = client.get("/health").json()
    a = health.get("analysis", {})
    backend = f"{a.get('backend')}" + (f"/{a.get('model')}" if a.get("model") else "")
    typer.secho(
        f"daemon: {health['status']} (v{health['version']}) @ {get_settings().base_url}  [analysis: {backend}]",
        fg=typer.colors.GREEN,
    )
    projects = _check(client.get("/projects")).json()
    if not projects:
        typer.echo("no projects registered")
        return
    typer.echo(f"\n{len(projects)} project(s):")
    for p in projects:
        runs = _check(client.get(f"/projects/{p['id']}/runs")).json()
        succeeded = sum(1 for r in runs if r["status"] == "succeeded")
        typer.echo(f"  {p['id']}  {p['name']:<20} default={p['default_branch']:<12} runs={len(runs)} ok={succeeded}")


# --- projects ------------------------------------------------------------------
@project_app.command("add")
def project_add(path: str, name: str = typer.Option(None, "--name", "-n")):
    """Register a git repo as a project (auto-analyzes the default branch)."""
    client = _require_daemon()
    p = _check(client.post("/projects", json={"path": path, "name": name})).json()
    typer.secho(f"added project {p['id']} ({p['name']}), default branch '{p['default_branch']}'", fg=typer.colors.GREEN)


@project_app.command("ls")
def project_ls():
    """List registered projects."""
    client = _require_daemon()
    projects = _check(client.get("/projects")).json()
    if not projects:
        typer.echo("no projects registered")
        return
    for p in projects:
        typer.echo(f"{p['id']}  {p['name']:<20} {p['path']}")


@project_app.command("rm")
def project_rm(project_id: str):
    """Remove a project."""
    client = _require_daemon()
    _check(client.delete(f"/projects/{project_id}"))
    typer.secho(f"removed project {project_id}", fg=typer.colors.GREEN)


# --- analysis ------------------------------------------------------------------
@app.command()
def analyze(
    project_id: str,
    branch: str = typer.Option(None, "--branch", "-b", help="Analyze a single branch"),
    all_branches: bool = typer.Option(False, "--all", help="Analyze every branch"),
    force: bool = typer.Option(False, "--force", help="Re-analyze even if up to date"),
):
    """Enqueue analysis for a project's branch(es)."""
    client = _require_daemon()
    body = {"branch": branch, "all": all_branches, "force": force}
    runs = _check(client.post(f"/projects/{project_id}/analyze", json=body)).json()
    if not runs:
        typer.echo("nothing enqueued (already up to date — use --force to re-run)")
        return
    typer.secho(f"enqueued {len(runs)} run(s):", fg=typer.colors.GREEN)
    for r in runs:
        typer.echo(f"  {r['id']}  {r['branch']}@{r['commit'][:8]}  [{r['status']}]")


# --- gold standard -------------------------------------------------------------
@gold_app.command("show")
def gold_show(
    project_id: str,
    output: str = typer.Option(None, "--output", "-o", help="Write to a file instead of stdout"),
):
    """Print the project's gold standard journey."""
    client = _require_daemon()
    journey = _check(client.get(f"/projects/{project_id}/gold")).json()
    text = json.dumps(journey, indent=2)
    if output:
        Path(output).write_text(text)
        typer.secho(f"wrote gold standard to {output}", fg=typer.colors.GREEN)
    else:
        typer.echo(text)


@gold_app.command("set")
def gold_set(project_id: str, json_file: str):
    """Insert or edit the gold standard from a Journey JSON file."""
    client = _require_daemon()
    try:
        payload = json.loads(Path(json_file).read_text())
    except (OSError, json.JSONDecodeError) as e:
        typer.secho(f"cannot read {json_file}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    _check(client.put(f"/projects/{project_id}/gold", json=payload))
    typer.secho(f"gold standard set for project {project_id}", fg=typer.colors.GREEN)


@gold_app.command("from-branch")
def gold_from_branch(
    project_id: str,
    branch: str = typer.Option(None, "--branch", "-b", help="Branch to analyze (default: project default branch)"),
):
    """Build the gold standard automatically by analyzing a branch."""
    client = _require_daemon()
    body = {"branch": branch}
    journey = _check(client.post(f"/projects/{project_id}/gold/from-branch", json=body)).json()
    src = journey.get("product", {}).get("source_commit", "?")
    typer.secho(f"gold standard built from commit {src[:8]}", fg=typer.colors.GREEN)


@gold_app.command("rm")
def gold_rm(project_id: str):
    """Remove the project's gold standard."""
    client = _require_daemon()
    _check(client.delete(f"/projects/{project_id}/gold"))
    typer.secho(f"removed gold standard for project {project_id}", fg=typer.colors.GREEN)


# --- comparison ----------------------------------------------------------------
_STATUS_COLOR = {
    "missing": typer.colors.RED,
    "added": typer.colors.GREEN,
    "changed": typer.colors.CYAN,
    "matched": typer.colors.WHITE,
}


def _print_report(rep: dict, show_matched: bool = False):
    typer.secho(rep["summary"], fg=typer.colors.BRIGHT_WHITE, bold=True)
    typer.echo(
        f"  coverage {rep['coverage']:.0%}  |  matched {rep['matched']}  changed {rep['changed']}"
        f"  missing {rep['missing']}  added {rep['added']}"
    )
    for d in rep["deltas"]:
        if d["status"] == "matched" and not show_matched:
            continue
        stage = d.get("target_stage") or d.get("candidate_stage") or "?"
        extra = ("  (" + "; ".join(d["changes"]) + ")") if d.get("changes") else ""
        typer.secho(f"  [{d['status']:<7}] {stage}/{d['name']}{extra}",
                    fg=_STATUS_COLOR.get(d["status"]))


@app.command()
def gap(
    project_id: str,
    branch: str,
    show_matched: bool = typer.Option(False, "--all", help="Also list matched milestones"),
):
    """Gap analysis: how far a branch is from the project's gold standard."""
    client = _require_daemon()
    rep = _check(client.get(f"/projects/{project_id}/branches/{branch}/gap")).json()
    _print_report(rep, show_matched)


@app.command()
def drift(
    project_id: str,
    base: str,
    head: str,
    show_matched: bool = typer.Option(False, "--all", help="Also list matched milestones"),
):
    """Drift analysis: how the head branch differs from the base branch."""
    client = _require_daemon()
    rep = _check(client.get(f"/projects/{project_id}/drift", params={"base": base, "head": head})).json()
    _print_report(rep, show_matched)


@app.command()
def runs(project_id: str):
    """List analysis runs for a project."""
    client = _require_daemon()
    items = _check(client.get(f"/projects/{project_id}/runs")).json()
    if not items:
        typer.echo("no runs")
        return
    for r in items:
        err = f"  ! {r['error']}" if r.get("error") else ""
        typer.echo(f"{r['id']}  {r['branch']:<20} {r['commit'][:8]}  {r['status']:<10}{err}")


if __name__ == "__main__":
    app()
