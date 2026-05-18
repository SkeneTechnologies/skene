"""Tests for the SchemaToolset (Step 1's read-side)."""

from __future__ import annotations

from pathlib import Path

import pytest

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.tools.schema_tools import SchemaToolset
from skene.analyzers.schema_parsers.models import (
    ColumnInfo,
    ForeignKey,
    SchemaIndex,
    TableInfo,
)


def _build_index() -> SchemaIndex:
    users = TableInfo(
        name="users",
        schema_file="public.sql",
        columns=[
            ColumnInfo(name="id", type="uuid", nullable=False),
            ColumnInfo(name="email", type="text", nullable=False),
            ColumnInfo(name="created_at", type="timestamptz", nullable=False),
        ],
        primary_key=["id"],
        foreign_keys=[],
    )
    estimates = TableInfo(
        name="estimates",
        schema_file="public.sql",
        columns=[
            ColumnInfo(name="id", type="uuid", nullable=False),
            ColumnInfo(name="user_id", type="uuid", nullable=False),
            ColumnInfo(name="amount", type="numeric", nullable=False),
        ],
        primary_key=["id"],
        foreign_keys=[
            ForeignKey(
                columns=["user_id"],
                references_table="users",
                references_columns=["id"],
            )
        ],
    )
    auth_users = TableInfo(
        name="users",
        schema_file="auth.sql",
        columns=[ColumnInfo(name="id", type="uuid", nullable=False)],
        primary_key=["id"],
    )
    index = SchemaIndex(
        files={
            "public.sql": [users, estimates],
            "auth.sql": [auth_users],
        }
    )
    return index


def test_list_schema_files_hides_internals():
    toolset = SchemaToolset(_build_index(), [])
    files = toolset._list_schema_files()
    names = [f.name for f in files]
    assert names == ["public.sql"]
    assert files[0].is_internal is False
    assert files[0].table_count == 2


def test_list_tables_returns_cheap_summaries():
    toolset = SchemaToolset(_build_index(), [])
    summaries = toolset._list_tables("public.sql")
    assert not isinstance(summaries, dict)
    by_name = {s.name: s for s in summaries}
    assert by_name["users"].has_created_at is True
    assert by_name["users"].has_user_fk is False
    assert by_name["estimates"].has_user_fk is True  # user_id column
    assert by_name["users"].pk_columns == ["id"]


def test_list_tables_unknown_file_returns_error():
    toolset = SchemaToolset(_build_index(), [])
    out = toolset._list_tables("does_not_exist.sql")
    assert isinstance(out, dict)
    assert "error" in out


def test_describe_table_returns_full_info():
    toolset = SchemaToolset(_build_index(), [])
    out = toolset._describe_table("public.sql", "estimates")
    assert isinstance(out, TableInfo)
    assert len(out.columns) == 3
    assert out.foreign_keys[0].references_table == "users"


def test_search_tables_substring_case_insensitive_across_files():
    toolset = SchemaToolset(_build_index(), [])
    hits = toolset._search_tables("USER")
    files = {h.schema_file for h in hits}
    assert files == {"public.sql", "auth.sql"}


def test_emit_milestone_appends_to_collector():
    collector: list[CandidateMilestone] = []
    toolset = SchemaToolset(_build_index(), collector)
    ack = toolset._emit_milestone(
        proposed_id="account_created",
        name="Account Created",
        description="New row in users table",
        table="public.users",
        reason="users table has email + created_at",
    )
    assert ack == "recorded account_created"
    assert len(collector) == 1
    cm = collector[0]
    assert cm.evidence[0].source.value == "db"
    assert cm.evidence[0].table == "public.users"


@pytest.mark.asyncio
async def test_as_tools_returns_callable_handlers():
    toolset = SchemaToolset(_build_index(), [])
    tools = toolset.as_tools()
    by_name = {t.name: t for t in tools}
    # The agent loop will invoke handler with a dict
    files = await by_name["list_schema_files"].handler({})
    assert isinstance(files, list)
    assert files[0]["name"] == "public.sql"


@pytest.mark.asyncio
async def test_emit_milestone_handler_records_into_collector():
    collector: list[CandidateMilestone] = []
    toolset = SchemaToolset(_build_index(), collector)
    by_name = {t.name: t for t in toolset.as_tools()}
    ack = await by_name["emit_milestone"].handler(
        {
            "proposed_id": "estimate_created",
            "name": "Estimate Created",
            "description": "User creates an estimate",
            "table": "public.estimates",
            "reason": "estimates table holds user-generated content",
            "confidence": 0.9,
        }
    )
    assert ack == "recorded estimate_created"
    assert collector[0].confidence == 0.9


@pytest.mark.asyncio
async def test_run_schema_agent_against_fixture():
    """Smoke test the agent over the real journeygen fixture using a scripted client."""
    from skene.analyzers.journey.schema_agent import run_schema_agent
    from skene.llm.agent_loop import AssistantTurn, Message, Tool, ToolCall
    from skene.llm.base import LLMClient

    fixture = Path("/Users/miche/skene/projects/journeygen/tests/fixtures/sample_schemas")
    if not fixture.exists():
        pytest.skip("journeygen fixture not available")

    class _ScriptedAgent(LLMClient):
        def __init__(self):
            self._step = 0

        async def generate_content_with_usage(self, prompt: str):
            return ("", None)

        async def generate_content_stream(self, prompt: str):
            if False:
                yield ""

        def get_model_name(self) -> str:
            return "scripted"

        def get_provider_name(self) -> str:
            return "scripted"

        async def generate_with_tools(self, messages: list[Message], tools: list[Tool]) -> AssistantTurn:
            self._step += 1
            if self._step == 1:
                return AssistantTurn(
                    text=None,
                    tool_calls=[ToolCall(id="c1", name="list_schema_files", arguments={})],
                )
            if self._step == 2:
                return AssistantTurn(
                    text=None,
                    tool_calls=[
                        ToolCall(
                            id="c2",
                            name="emit_milestone",
                            arguments={
                                "proposed_id": "account_created",
                                "name": "Account Created",
                                "description": "First user row in public.users",
                                "table": "public.users",
                                "reason": "users table exists with auth fields",
                                "confidence": 0.9,
                            },
                        )
                    ],
                )
            return AssistantTurn(text="done")

    client = _ScriptedAgent()
    candidates = await run_schema_agent(fixture, client, max_turns=10)
    assert len(candidates) == 1
    assert candidates[0].proposed_id == "account_created"
    assert candidates[0].evidence[0].source.value == "db"
