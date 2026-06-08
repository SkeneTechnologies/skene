"""DaemonService — wires registry, git, analyzer, job queue and storage together and
exposes the high-level operations the API and CLI call.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import git_service as git
from .analyzer import Analyzer, AnalysisContext
from .comparison import ComparisonReport, compare_journeys
from .config import Settings, get_settings
from .journey_pipeline import JourneyPipeline, JourneyPipelineAnalyzer, build_pipeline
from .db import Database
from .journey import Journey
from .jobs import JobQueue
from .models import AnalysisRun, BranchInfo, JobStatus, Project, RunKind, utcnow
from .monitor import WorkingBranchMonitor
from .registry import ProjectRegistry
from .storage import Storage

logger = logging.getLogger("skened.service")


class ServiceError(RuntimeError):
    pass


class NotFoundError(ServiceError):
    pass


# Settings that can be changed at runtime (via the dashboard / PATCH /settings).
_EDITABLE_SETTINGS = (
    "analysis_backend", "llm_model", "llm_api_key", "llm_base_url", "llm_temperature",
    "monitor_enabled", "monitor_interval", "monitor_on_commit",
)
# Subset whose change requires rebuilding the analysis pipeline.
_PIPELINE_KEYS = ("analysis_backend", "llm_model", "llm_api_key", "llm_base_url", "llm_temperature")


class DaemonService:
    def __init__(
        self,
        settings: Settings | None = None,
        analyzer: Analyzer | None = None,
        pipeline: JourneyPipeline | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.db = Database(self.settings.db_path)
        self.registry = ProjectRegistry(self.db)
        self.storage = Storage(self.settings)
        self._apply_settings_overlay()  # persisted dashboard overrides, before building the pipeline
        # Full from-scratch analysis (default branch + gold) uses ``analyzer``; branch-diff
        # uses ``pipeline`` directly. They share one JourneyPipeline, built from settings
        # (heuristic or LLM backend) unless one is injected.
        self.pipeline = pipeline or build_pipeline(self.settings)
        self.analyzer: Analyzer = analyzer or JourneyPipelineAnalyzer(self.pipeline)
        self.queue = JobQueue(self._execute_run, concurrency=self.settings.worker_concurrency)
        # Always constructed; ticks idle when monitor_enabled is False (toggled live).
        self.monitor = WorkingBranchMonitor(self)

    def analysis_info(self) -> dict:
        """Effective analysis configuration — surfaced via /health and `skene config`."""
        return {
            "backend": self.settings.analysis_backend,
            "llm_enabled": self.settings.llm_enabled,
            "model": self.settings.llm_model,
            "extractor": type(self.pipeline.extractor).__name__,
            "classifier": type(self.pipeline.classifier).__name__,
            "brancher": type(self.pipeline.brancher).__name__ if self.pipeline.brancher else None,
        }

    # --- runtime settings ----------------------------------------------------
    def settings_public(self) -> dict:
        """Editable settings for the dashboard. The API key is never returned — only whether
        one is set."""
        s = self.settings
        return {
            "analysis_backend": s.analysis_backend,
            "llm_enabled": s.llm_enabled,
            "llm_model": s.llm_model,
            "llm_api_key_set": bool(s.llm_api_key),
            "llm_base_url": s.llm_base_url,
            "llm_temperature": s.llm_temperature,
            "monitor_enabled": s.monitor_enabled,
            "monitor_interval": s.monitor_interval,
            "monitor_on_commit": s.monitor_on_commit,
        }

    def update_settings(self, updates: dict) -> dict:
        """Apply a partial settings update, rebuilding the pipeline if an LLM/backend field
        changed, then persist the change so it survives a restart. Validation failures (e.g.
        backend='llm' with no model) raise ServiceError and leave state untouched."""
        clean = {k: _coerce_setting(k, v) for k, v in updates.items() if k in _EDITABLE_SETTINGS}
        if not clean:
            return self.settings_public()

        candidate = self.settings.model_copy(update=clean)
        pipeline_changed = any(
            getattr(self.settings, k) != getattr(candidate, k) for k in _PIPELINE_KEYS
        )
        new_pipeline = None
        if pipeline_changed:
            try:
                new_pipeline = build_pipeline(candidate)  # validates LLM config
            except ValueError as e:
                raise ServiceError(str(e)) from e

        for k, v in clean.items():
            setattr(self.settings, k, v)
        if new_pipeline is not None:
            self.pipeline = new_pipeline
            self.analyzer = JourneyPipelineAnalyzer(self.pipeline)

        self._persist_settings_overlay(clean)
        logger.info("settings updated: %s", sorted(clean))
        return self.settings_public()

    def _overlay_path(self) -> Path:
        return self.settings.data_dir / "settings.json"

    def _apply_settings_overlay(self) -> None:
        path = self._overlay_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            logger.warning("ignoring unreadable settings overlay %s", path)
            return
        for k, v in data.items():
            if k in _EDITABLE_SETTINGS:
                setattr(self.settings, k, v)

    def _persist_settings_overlay(self, clean: dict) -> None:
        """Merge the just-changed fields into the on-disk overlay (sparse — only fields set
        via the dashboard persist; everything else still comes from env/defaults)."""
        path = self._overlay_path()
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                data = {}
        data.update(clean)
        path.write_text(json.dumps(data, indent=2))
        try:
            os.chmod(path, 0o600)  # may hold an API key — keep it user-only
        except OSError:
            pass

    async def start(self) -> None:
        await self.queue.start()
        if self.monitor is not None:
            await self.monitor.start()

    async def stop(self) -> None:
        if self.monitor is not None:
            await self.monitor.stop()
        await self.queue.stop()
        self.db.close()

    # --- projects ------------------------------------------------------------
    async def add_project(self, path: str, name: str | None = None) -> Project:
        project = await self.registry.add_project(path, name)
        # Auto-analyze the default branch only (avoid surprise load on big repos).
        await self.enqueue_analysis(project.id, branch=project.default_branch)
        return project

    def get_project(self, project_id: str) -> Project:
        project = self.registry.get_project(project_id)
        if project is None:
            raise NotFoundError(f"project not found: {project_id}")
        return project

    def list_projects(self) -> list[Project]:
        return self.registry.list_projects()

    def remove_project(self, project_id: str) -> bool:
        return self.registry.remove_project(project_id)

    # --- branches ------------------------------------------------------------
    async def list_branches(self, project_id: str) -> list[BranchInfo]:
        project = self.get_project(project_id)
        repo = Path(project.path)
        current = await git.current_branch(repo)
        branches: list[BranchInfo] = []
        for b in await git.list_branches(repo):
            latest = self.db.latest_run_for_branch(project_id, b.name)
            succeeded = self.db.latest_run_for_branch(project_id, b.name, JobStatus.succeeded)
            branches.append(
                BranchInfo(
                    name=b.name,
                    head_commit=b.commit,
                    is_current=(b.name == current),
                    is_default=(b.name == project.default_branch),
                    last_analyzed_commit=succeeded.commit if succeeded else None,
                    last_commit_at=(
                        datetime.fromtimestamp(b.committed_at, tz=timezone.utc)
                        if b.committed_at is not None else None
                    ),
                    status=latest.status if latest else None,
                    up_to_date=bool(succeeded and succeeded.commit == b.commit),
                )
            )
        # Pin the current branch, then the default, then order by most-recent commit.
        branches.sort(key=lambda x: (
            0 if x.is_current else 1 if x.is_default else 2,
            -(x.last_commit_at.timestamp() if x.last_commit_at else 0.0),
            x.name,
        ))
        return branches

    async def get_branch_journey(self, project_id: str, branch: str) -> Journey:
        self.get_project(project_id)
        run = self.db.latest_run_for_branch(project_id, branch, JobStatus.succeeded)
        if run is None or not run.journey_path:
            raise NotFoundError(f"no completed analysis for branch '{branch}'")
        return self.storage.load_journey(Path(run.journey_path))

    # --- analysis ------------------------------------------------------------
    async def enqueue_analysis(
        self,
        project_id: str,
        *,
        branch: str | None = None,
        all_branches: bool = False,
        force: bool = False,
    ) -> list[AnalysisRun]:
        project = self.get_project(project_id)
        repo = Path(project.path)

        if all_branches:
            targets = [b.name for b in await git.list_branches(repo)]
        elif branch:
            targets = [branch]
        else:
            raise ServiceError("specify a branch or all_branches=True")

        runs: list[AnalysisRun] = []
        for name in targets:
            try:
                commit = await git.head_commit(repo, name)
            except git.GitError as e:
                raise ServiceError(str(e)) from e

            if not force:
                done = self.db.latest_run_for_branch(project_id, name, JobStatus.succeeded)
                if done and done.commit == commit:
                    logger.info("skip %s@%s — already analyzed", name, commit[:8])
                    continue

            run = AnalysisRun(
                id=uuid.uuid4().hex[:12],
                project_id=project_id,
                kind=RunKind.branch,
                branch=name,
                commit=commit,
            )
            self.db.insert_run(run)
            self.queue.enqueue(run.id)
            runs.append(run)
        return runs

    def get_run(self, run_id: str) -> AnalysisRun:
        run = self.db.get_run(run_id)
        if run is None:
            raise NotFoundError(f"run not found: {run_id}")
        return run

    def list_runs(self, project_id: str) -> list[AnalysisRun]:
        self.get_project(project_id)
        return self.db.list_runs(project_id)

    # --- comparison: gap (vs gold) and drift (branch vs branch) --------------
    async def gap(self, project_id: str, branch: str) -> ComparisonReport:
        """How far branch ``branch`` is from the project's gold standard."""
        gold = self.get_gold(project_id)                      # NotFoundError if unset
        branch_journey = await self.get_branch_journey(project_id, branch)
        return compare_journeys(
            gold, branch_journey, kind="gap",
            target_label="gold", candidate_label=branch,
        )

    async def drift(self, project_id: str, base_branch: str, head_branch: str) -> ComparisonReport:
        """How branch ``head_branch`` has drifted from ``base_branch``."""
        base = await self.get_branch_journey(project_id, base_branch)
        head = await self.get_branch_journey(project_id, head_branch)
        return compare_journeys(
            base, head, kind="drift",
            target_label=base_branch, candidate_label=head_branch,
        )

    # --- gold standard -------------------------------------------------------
    def get_gold(self, project_id: str) -> Journey:
        self.get_project(project_id)
        gold = self.storage.load_gold(project_id)
        if gold is None:
            raise NotFoundError(f"no gold standard set for project {project_id}")
        return gold

    def has_gold(self, project_id: str) -> bool:
        return self.storage.gold_path(project_id).exists()

    def set_gold(self, project_id: str, journey: Journey) -> Journey:
        """Manually insert or edit the gold standard (full replacement)."""
        self.get_project(project_id)
        self.storage.save_gold(project_id, journey)
        return journey

    async def create_gold_from_branch(self, project_id: str, branch: str | None = None) -> Journey:
        """Build the gold standard by analyzing a branch (defaults to the project's
        default branch). Reuses an existing journey for the branch's current HEAD when
        available, otherwise analyzes synchronously."""
        project = self.get_project(project_id)
        branch = branch or project.default_branch
        repo = Path(project.path)
        try:
            commit = await git.head_commit(repo, branch)
        except git.GitError as e:
            raise ServiceError(str(e)) from e

        # Gold is a reference target → always a from-scratch FULL analysis, never a
        # branch-diff. Reuse a stored run only for the default branch, whose runs are
        # themselves full-pipeline.
        journey: Journey | None = None
        if branch == project.default_branch:
            done = self.db.latest_run_for_branch(project_id, branch, JobStatus.succeeded)
            if done and done.commit == commit and done.journey_path and Path(done.journey_path).exists():
                journey = self.storage.load_journey(Path(done.journey_path))
        if journey is None:
            journey = await self._full_pipeline(project, branch, commit)

        self.storage.save_gold(project_id, journey)
        return journey

    def delete_gold(self, project_id: str) -> bool:
        self.get_project(project_id)
        path = self.storage.gold_path(project_id)
        if path.exists():
            path.unlink()
            return True
        return False

    # --- worker executor -----------------------------------------------------
    async def _execute_run(self, run_id: str) -> None:
        run = self.db.get_run(run_id)
        if run is None:
            logger.warning("run %s vanished before execution", run_id)
            return
        project = self.db.get_project(run.project_id)
        if project is None:
            logger.warning("project %s gone; marking run %s failed", run.project_id, run_id)
            run.status = JobStatus.failed
            run.error = "project removed"
            run.finished_at = utcnow()
            self.db.update_run(run)
            return

        run.status = JobStatus.running
        run.started_at = utcnow()
        self.db.update_run(run)

        try:
            journey = await self._analyze_branch(project, run.branch, run.commit)
            path = self.storage.save_journey(project.id, run.branch, run.commit, journey)
            run.status = JobStatus.succeeded
            run.journey_path = str(path)
        except Exception as e:  # noqa: BLE001 — record failure, never crash the worker
            logger.exception("analysis failed for run %s", run_id)
            run.status = JobStatus.failed
            run.error = str(e)
        finally:
            run.finished_at = utcnow()
            self.db.update_run(run)

    async def _analyze_branch(self, project: Project, branch: str, commit: str) -> Journey:
        """Resolve the base this analysis builds on, then derive via the branch-from logic.

        - **Branch already analyzed + new commit → incremental**: branch from the branch's
          OWN previous journey, applying only the diff since the last analyzed commit.
        - **First analysis of the default branch → full from-scratch pipeline** (the root base).
        - **First analysis of any other branch → branch from the default branch's journey.**
        """
        prev = self._latest_branch_journey(project.id, branch)
        if prev is not None and prev[0] != commit:
            base_commit, base_journey = prev
            return await self._branch_from_base(
                project, branch, commit, base_commit, base_journey, base_label=branch)

        if branch == project.default_branch:
            return await self._full_pipeline(project, branch, commit)

        base_commit, base_journey = await self._ensure_default_base(project)
        return await self._branch_from_base(
            project, branch, commit, base_commit, base_journey, base_label=project.default_branch)

    async def _full_pipeline(self, project: Project, branch: str, commit: str) -> Journey:
        """Full from-scratch analysis of ``commit`` in an isolated worktree (default branch
        + gold). Always cleans up the worktree, leaving the user's checkout untouched."""
        repo = Path(project.path)
        dest = self._worktree_path(project.id, commit)
        try:
            await git.add_worktree(repo, commit, dest)
            ctx = AnalysisContext(
                project_name=project.name, branch=branch, commit=commit, worktree_path=dest,
            )
            return await self.analyzer.analyze(ctx)
        finally:
            await git.remove_worktree(repo, dest)

    async def _branch_from_base(
        self,
        project: Project,
        branch: str,
        commit: str,
        base_commit: str,
        base_journey: Journey,
        base_label: str,
    ) -> Journey:
        """Derive ``branch``@``commit`` from ``base_journey`` (built at ``base_commit``) by
        diffing ``base_commit..commit`` and handing both to the pipeline's brancher."""
        repo = Path(project.path)
        rows = await git.diff_name_status(repo, base_commit, commit)
        changed, removed = _split_diff(rows)
        diff_text = await git.diff(repo, base_commit, commit)

        dest = self._worktree_path(project.id, commit)
        try:
            await git.add_worktree(repo, commit, dest)
            return await self.pipeline.branch_from(
                base_journey, dest,
                changed_paths=changed, removed_paths=removed,
                product_name=project.name, base_branch=base_label,
                source_commit=commit, diff_text=diff_text,
            )
        finally:
            await git.remove_worktree(repo, dest)

    async def _ensure_default_base(self, project: Project) -> tuple[str, Journey]:
        """The default branch's latest journey, building it on the fly if none exists yet."""
        base = self._latest_branch_journey(project.id, project.default_branch)
        if base is not None:
            return base
        repo = Path(project.path)
        base_commit = await git.head_commit(repo, project.default_branch)
        base_journey = await self._full_pipeline(project, project.default_branch, base_commit)
        self.storage.save_journey(project.id, project.default_branch, base_commit, base_journey)
        logger.info("built base journey for %s on the fly at %s", project.default_branch, base_commit[:8])
        return base_commit, base_journey

    def _worktree_path(self, project_id: str, commit: str) -> Path:
        # Unique per call so concurrent analyses (e.g. `--all`) never collide on a path,
        # even when they target the same commit.
        return self.settings.worktrees_dir / project_id / f"{commit}-{uuid.uuid4().hex[:8]}"

    def _latest_branch_journey(self, project_id: str, branch: str) -> tuple[str, Journey] | None:
        run = self.db.latest_run_for_branch(project_id, branch, JobStatus.succeeded)
        if run and run.journey_path and Path(run.journey_path).exists():
            return run.commit, self.storage.load_journey(Path(run.journey_path))
        return None


def _coerce_setting(key: str, value):
    # Treat a blank string from a form field as "unset" for the optional LLM fields.
    if key in ("llm_model", "llm_api_key", "llm_base_url") and value == "":
        return None
    return value


def _split_diff(rows: list[list[str]]) -> tuple[set[str], set[str]]:
    """Split ``git diff --name-status`` rows into (changed, removed) repo-relative paths.

    Added/modified/type-changed → changed. Deleted → removed. Renamed → old removed,
    new changed. Copied → new changed (original untouched).
    """
    changed: set[str] = set()
    removed: set[str] = set()
    for parts in rows:
        if not parts:
            continue
        code = parts[0][0]
        if code in ("A", "M", "T") and len(parts) >= 2:
            changed.add(parts[1])
        elif code == "D" and len(parts) >= 2:
            removed.add(parts[1])
        elif code == "R" and len(parts) >= 3:
            removed.add(parts[1])
            changed.add(parts[2])
        elif code == "C" and len(parts) >= 3:
            changed.add(parts[2])
    return changed, removed
