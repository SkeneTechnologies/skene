"""SQLite persistence for sessions, messages, and parts.

Plain relational state (the design doc's "take, simplified" verdict on
opencode's persistence): every row stores the full wire-model JSON in a
``data`` column plus the handful of columns queries filter on. Writers
mutate state here and publish a bus event — there is no event-sourcing
layer to replay.

One global DB (default ``~/.local/share/skene/skene.db``, WAL mode) holds
every workspace; rows are scoped through ``project.directory``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import aiosqlite
from pydantic import TypeAdapter

from skene.core.bus import normalize_directory
from skene.schema import Message, Part, Project, Session, new_id

DEFAULT_DB_PATH = Path("~/.local/share/skene/skene.db").expanduser()

_MESSAGE_ADAPTER: TypeAdapter[Message] = TypeAdapter(Message)
_PART_ADAPTER: TypeAdapter[Part] = TypeAdapter(Part)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
    id        TEXT PRIMARY KEY,
    directory TEXT NOT NULL UNIQUE,
    name      TEXT,
    created   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS session (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id),
    parent_id  TEXT,
    agent      TEXT NOT NULL,
    title      TEXT,
    status     TEXT NOT NULL,
    created    INTEGER NOT NULL,
    updated    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_project ON session(project_id, created);
CREATE INDEX IF NOT EXISTS idx_session_parent  ON session(parent_id);
CREATE TABLE IF NOT EXISTS message (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES session(id),
    role       TEXT NOT NULL,
    created    INTEGER NOT NULL,
    data       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_message_session ON message(session_id, created);
CREATE TABLE IF NOT EXISTS part (
    id         TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES message(id),
    session_id TEXT NOT NULL,
    type       TEXT NOT NULL,
    created    INTEGER NOT NULL,
    data       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_part_message ON part(message_id, created);
"""


def now_ms() -> int:
    return int(time.time() * 1000)


class UnknownSessionError(KeyError):
    """Raised when a session id does not exist."""


class Store:
    """Async SQLite store. Create via :meth:`open`, dispose via :meth:`close`."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    @classmethod
    async def open(cls, path: Path | str = DEFAULT_DB_PATH) -> "Store":
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.executescript(_SCHEMA)
        await db.commit()
        return cls(db)

    async def close(self) -> None:
        await self._db.close()

    # -- projects -----------------------------------------------------------

    async def ensure_project(self, directory: str | Path) -> Project:
        """Get or create the project row for a workspace directory."""
        directory = normalize_directory(directory)
        async with self._db.execute("SELECT * FROM project WHERE directory = ?", (directory,)) as cur:
            row = await cur.fetchone()
        if row is not None:
            return Project(id=row["id"], directory=row["directory"], name=row["name"])
        project = Project(id=new_id("prj"), directory=directory, name=Path(directory).name or None)
        await self._db.execute(
            "INSERT INTO project (id, directory, name, created) VALUES (?, ?, ?, ?)",
            (project.id, project.directory, project.name, now_ms()),
        )
        await self._db.commit()
        return project

    async def project_directory(self, project_id: str) -> str | None:
        async with self._db.execute("SELECT directory FROM project WHERE id = ?", (project_id,)) as cur:
            row = await cur.fetchone()
        return row["directory"] if row else None

    # -- sessions -----------------------------------------------------------

    @staticmethod
    def _session_from_row(row: aiosqlite.Row) -> Session:
        return Session(
            id=row["id"],
            project_id=row["project_id"],
            parent_id=row["parent_id"],
            agent=row["agent"],
            title=row["title"],
            status=row["status"],
            created=row["created"],
            updated=row["updated"],
        )

    async def create_session(
        self,
        *,
        project_id: str,
        agent: str,
        parent_id: str | None = None,
        title: str | None = None,
    ) -> Session:
        ts = now_ms()
        session = Session(
            id=new_id("ses"),
            project_id=project_id,
            parent_id=parent_id,
            agent=agent,
            title=title,
            status="idle",
            created=ts,
            updated=ts,
        )
        await self._db.execute(
            "INSERT INTO session (id, project_id, parent_id, agent, title, status, created, updated)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session.id,
                session.project_id,
                session.parent_id,
                session.agent,
                session.title,
                session.status,
                session.created,
                session.updated,
            ),
        )
        await self._db.commit()
        return session

    async def get_session(self, session_id: str) -> Session:
        async with self._db.execute("SELECT * FROM session WHERE id = ?", (session_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise UnknownSessionError(session_id)
        return self._session_from_row(row)

    async def update_session(self, session: Session) -> Session:
        session = session.model_copy(update={"updated": now_ms()})
        await self._db.execute(
            "UPDATE session SET title = ?, status = ?, updated = ? WHERE id = ?",
            (session.title, session.status, session.updated, session.id),
        )
        await self._db.commit()
        return session

    async def list_sessions(self, *, project_id: str | None = None) -> list[Session]:
        if project_id is None:
            query, args = "SELECT * FROM session ORDER BY created", ()
        else:
            query, args = "SELECT * FROM session WHERE project_id = ? ORDER BY created", (project_id,)
        async with self._db.execute(query, args) as cur:
            rows = await cur.fetchall()
        return [self._session_from_row(r) for r in rows]

    async def list_children(self, parent_id: str) -> list[Session]:
        async with self._db.execute("SELECT * FROM session WHERE parent_id = ? ORDER BY created", (parent_id,)) as cur:
            rows = await cur.fetchall()
        return [self._session_from_row(r) for r in rows]

    async def session_directory(self, session_id: str) -> str:
        """Workspace directory a session belongs to (for event scoping)."""
        async with self._db.execute(
            "SELECT p.directory FROM session s JOIN project p ON p.id = s.project_id WHERE s.id = ?",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise UnknownSessionError(session_id)
        return row["directory"]

    # -- messages & parts ----------------------------------------------------

    async def save_message(self, message: Message) -> None:
        """Insert or replace a message (updates rewrite the full JSON)."""
        await self._db.execute(
            "INSERT INTO message (id, session_id, role, created, data) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (message.id, message.session_id, message.role, message.created, message.model_dump_json()),
        )
        await self._db.commit()

    async def save_part(self, part: Part) -> None:
        """Insert or replace a part (tool-state transitions rewrite the JSON)."""
        await self._db.execute(
            "INSERT INTO part (id, message_id, session_id, type, created, data) VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (part.id, part.message_id, part.session_id, part.type, now_ms(), part.model_dump_json()),
        )
        await self._db.commit()

    async def list_messages(self, session_id: str) -> list[tuple[Message, list[Part]]]:
        """Messages in creation order, each with its parts in creation order."""
        async with self._db.execute(
            "SELECT data FROM message WHERE session_id = ? ORDER BY created, id", (session_id,)
        ) as cur:
            message_rows = await cur.fetchall()
        async with self._db.execute(
            "SELECT message_id, data FROM part WHERE session_id = ? ORDER BY created, id", (session_id,)
        ) as cur:
            part_rows = await cur.fetchall()

        parts_by_message: dict[str, list[Part]] = {}
        for row in part_rows:
            parts_by_message.setdefault(row["message_id"], []).append(_PART_ADAPTER.validate_json(row["data"]))
        result: list[tuple[Message, list[Part]]] = []
        for row in message_rows:
            message = _MESSAGE_ADAPTER.validate_json(row["data"])
            result.append((message, parts_by_message.get(message.id, [])))
        return result

    # -- diagnostics ----------------------------------------------------------

    async def counts(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for table in ("project", "session", "message", "part"):
            async with self._db.execute(f"SELECT COUNT(*) AS n FROM {table}") as cur:  # noqa: S608
                row = await cur.fetchone()
            out[table] = row["n"]
        return out
