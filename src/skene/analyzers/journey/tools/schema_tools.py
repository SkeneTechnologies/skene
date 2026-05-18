"""Tools the schema agent uses to explore a parsed SchemaIndex.

Design points:
- ``list_tables`` returns a cheap :class:`TableSummary` (no column types) so
  triage is fast. The agent calls ``describe_table`` only for tables that
  look lifecycle-relevant.
- ``search_tables`` lets the agent locate concepts like "subscription" or
  "referral" without iterating every file.
- ``emit_milestone`` is the only output path. There is no final JSON blob —
  the agent stops emitting and the collector list holds the result.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.models import Evidence
from skene.analyzers.schema_parsers.models import SchemaFileInfo, SchemaIndex, TableInfo
from skene.llm.agent_loop import Tool
from skene.output import debug


class TableSummary(BaseModel):
    """Cheap overview — no column types. Used for triage."""

    name: str
    column_count: int
    has_created_at: bool
    has_user_fk: bool
    pk_columns: list[str] = Field(default_factory=list)


class TableRef(BaseModel):
    schema_file: str
    table: str


_TIMESTAMP_HINTS = ("created_at", "inserted_at")
_USER_HINTS = ("user", "owner", "account", "profile")


def _summarize_table(t: TableInfo) -> TableSummary:
    col_names = {c.name.lower() for c in t.columns}
    has_created_at = any(h in col_names for h in _TIMESTAMP_HINTS)
    has_user_fk = False
    for fk in t.foreign_keys:
        ref = fk.references_table.lower()
        if any(h in ref for h in _USER_HINTS):
            has_user_fk = True
            break
    if not has_user_fk:
        for c in t.columns:
            lc = c.name.lower()
            if lc.endswith("_id") and any(h in lc for h in _USER_HINTS):
                has_user_fk = True
                break
    return TableSummary(
        name=t.name,
        column_count=len(t.columns),
        has_created_at=has_created_at,
        has_user_fk=has_user_fk,
        pk_columns=list(t.primary_key),
    )


class SchemaToolset:
    """Holds the parsed index + a collector list for emitted milestones."""

    def __init__(self, index: SchemaIndex, collector: list[CandidateMilestone]) -> None:
        self._index = index
        self._collector = collector

    # --- Internal implementations (used directly by tests + the tool handlers) ---

    def _list_schema_files(self) -> list[SchemaFileInfo]:
        out: list[SchemaFileInfo] = []
        for name in self._index.application_files():
            info = self._index.file_info(name)
            if info is not None:
                out.append(info)
        return out

    def _list_tables(self, schema_file: str) -> list[TableSummary] | dict[str, str]:
        tables = self._index.files.get(schema_file)
        if tables is None:
            return {"error": f"unknown schema_file: {schema_file!r}"}
        return [_summarize_table(t) for t in tables]

    def _describe_table(self, schema_file: str, table: str) -> TableInfo | dict[str, str]:
        t = self._index.get_table(schema_file, table)
        if t is None:
            return {"error": f"unknown table {table!r} in {schema_file!r}"}
        return t

    def _search_tables(self, query: str) -> list[TableRef]:
        q = query.lower()
        out: list[TableRef] = []
        for fname, tables in self._index.files.items():
            for t in tables:
                if q in t.name.lower():
                    out.append(TableRef(schema_file=fname, table=t.name))
        return out

    def _emit_milestone(
        self,
        proposed_id: str,
        name: str,
        description: str,
        table: str,
        reason: str,
        tracked_event: str | None = None,
        confidence: float = 0.8,
    ) -> str:
        cm = CandidateMilestone(
            proposed_id=proposed_id,
            name=name,
            description=description,
            evidence=[Evidence(source="db", table=table, reason=reason)],
            tracked_event=tracked_event,
            confidence=confidence,
        )
        self._collector.append(cm)
        debug(f"schema tool: emit_milestone id={proposed_id} name={name!r} table={table} conf={confidence:.2f}")
        return f"recorded {proposed_id}"

    # --- Tool bindings ---

    def as_tools(self) -> list[Tool]:
        toolset = self

        def _dump_model(obj: Any) -> Any:
            if isinstance(obj, BaseModel):
                return obj.model_dump(mode="json")
            if isinstance(obj, list):
                return [_dump_model(x) for x in obj]
            return obj

        async def list_schema_files(args: dict[str, Any]) -> Any:
            debug("schema tool: list_schema_files()")
            return _dump_model(toolset._list_schema_files())

        async def list_tables(args: dict[str, Any]) -> Any:
            schema_file = args.get("schema_file", "")
            debug(f"schema tool: list_tables({schema_file!r})")
            return _dump_model(toolset._list_tables(schema_file))

        async def describe_table(args: dict[str, Any]) -> Any:
            schema_file = args.get("schema_file", "")
            table = args.get("table", "")
            debug(f"schema tool: describe_table({schema_file!r}, {table!r})")
            return _dump_model(toolset._describe_table(schema_file, table))

        async def search_tables(args: dict[str, Any]) -> Any:
            query = args.get("query", "")
            debug(f"schema tool: search_tables({query!r})")
            return _dump_model(toolset._search_tables(query))

        async def emit_milestone(args: dict[str, Any]) -> str:
            return toolset._emit_milestone(
                proposed_id=args["proposed_id"],
                name=args["name"],
                description=args["description"],
                table=args["table"],
                reason=args["reason"],
                tracked_event=args.get("tracked_event"),
                confidence=float(args.get("confidence", 0.8)),
            )

        return [
            Tool(
                name="list_schema_files",
                description=(
                    "List the application schema files. Supabase internal "
                    "schemas (auth, storage, realtime, ...) are hidden."
                ),
                parameters={"type": "object", "properties": {}},
                handler=list_schema_files,
            ),
            Tool(
                name="list_tables",
                description=(
                    "Per-table summary for the given schema_file. Returns "
                    "name, column_count, has_created_at, has_user_fk, "
                    "pk_columns. No column types — use describe_table for those."
                ),
                parameters={
                    "type": "object",
                    "properties": {"schema_file": {"type": "string"}},
                    "required": ["schema_file"],
                },
                handler=list_tables,
            ),
            Tool(
                name="describe_table",
                description=(
                    "Full detail for one table: columns (with types), primary key, foreign keys, and indexes."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "schema_file": {"type": "string"},
                        "table": {"type": "string"},
                    },
                    "required": ["schema_file", "table"],
                },
                handler=describe_table,
            ),
            Tool(
                name="search_tables",
                description=(
                    "Case-insensitive substring search for tables across every schema file, internal schemas included."
                ),
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                handler=search_tables,
            ),
            Tool(
                name="emit_milestone",
                description=(
                    "Record a candidate milestone. `table` is the DB "
                    "evidence — the table that proves the milestone "
                    "exists. The only way to produce output."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "proposed_id": {
                            "type": "string",
                            "description": "lowercase snake_case identifier",
                        },
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "table": {"type": "string"},
                        "reason": {"type": "string"},
                        "tracked_event": {"type": "string"},
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                    "required": [
                        "proposed_id",
                        "name",
                        "description",
                        "table",
                        "reason",
                    ],
                },
                handler=emit_milestone,
            ),
        ]
