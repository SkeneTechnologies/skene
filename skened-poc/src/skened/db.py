"""SQLite persistence for projects and analysis runs.

Deliberately tiny: stdlib ``sqlite3`` + a lock, no ORM. Synchronous methods are wrapped
with ``asyncio.to_thread`` by callers in async contexts; state volume is small so this is
plenty for a POC.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .models import AnalysisRun, JobStatus, Project, RunKind

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    path           TEXT NOT NULL,
    default_branch TEXT NOT NULL,
    github_remote  TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    kind         TEXT NOT NULL,
    branch       TEXT NOT NULL,
    "commit"     TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    finished_at  TEXT,
    error        TEXT,
    journey_path TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project_id);
CREATE INDEX IF NOT EXISTS idx_runs_branch ON runs(project_id, branch);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- projects ------------------------------------------------------------
    def insert_project(self, p: Project) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO projects (id, name, path, default_branch, github_remote, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (p.id, p.name, p.path, p.default_branch, p.github_remote, p.created_at.isoformat()),
            )
            self._conn.commit()

    def get_project(self, project_id: str) -> Project | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return _row_to_project(row) if row else None

    def list_projects(self) -> list[Project]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM projects ORDER BY created_at").fetchall()
        return [_row_to_project(r) for r in rows]

    def delete_project(self, project_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # --- runs ----------------------------------------------------------------
    def insert_run(self, r: AnalysisRun) -> None:
        with self._lock:
            self._conn.execute(
                'INSERT INTO runs (id, project_id, kind, branch, "commit", status, created_at,'
                " started_at, finished_at, error, journey_path)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    r.id, r.project_id, r.kind.value, r.branch, r.commit, r.status.value,
                    r.created_at.isoformat(),
                    r.started_at.isoformat() if r.started_at else None,
                    r.finished_at.isoformat() if r.finished_at else None,
                    r.error, r.journey_path,
                ),
            )
            self._conn.commit()

    def update_run(self, r: AnalysisRun) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET status = ?, started_at = ?, finished_at = ?, error = ?,"
                " journey_path = ? WHERE id = ?",
                (
                    r.status.value,
                    r.started_at.isoformat() if r.started_at else None,
                    r.finished_at.isoformat() if r.finished_at else None,
                    r.error, r.journey_path, r.id,
                ),
            )
            self._conn.commit()

    def get_run(self, run_id: str) -> AnalysisRun | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None

    def list_runs(self, project_id: str) -> list[AnalysisRun]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM runs WHERE project_id = ? ORDER BY created_at DESC", (project_id,)
            ).fetchall()
        return [_row_to_run(r) for r in rows]

    def latest_run_for_branch(
        self, project_id: str, branch: str, status: JobStatus | None = None
    ) -> AnalysisRun | None:
        query = "SELECT * FROM runs WHERE project_id = ? AND branch = ?"
        params: list[object] = [project_id, branch]
        if status is not None:
            query += " AND status = ?"
            params.append(status.value)
        query += " ORDER BY created_at DESC LIMIT 1"
        with self._lock:
            row = self._conn.execute(query, params).fetchone()
        return _row_to_run(row) if row else None


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        path=row["path"],
        default_branch=row["default_branch"],
        github_remote=row["github_remote"],
        created_at=row["created_at"],
    )


def _row_to_run(row: sqlite3.Row) -> AnalysisRun:
    return AnalysisRun(
        id=row["id"],
        project_id=row["project_id"],
        kind=RunKind(row["kind"]),
        branch=row["branch"],
        commit=row["commit"],
        status=JobStatus(row["status"]),
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error=row["error"],
        journey_path=row["journey_path"],
    )
