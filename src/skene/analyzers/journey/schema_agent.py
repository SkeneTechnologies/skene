"""Step 1 — Schema agent.

Parses every ``.sql`` file in ``schema_dir`` once, then hands the
:class:`SchemaIndex` to the LLM through five tools (see
:mod:`skene.analyzers.journey.tools.schema_tools`). The agent calls
``emit_milestone`` for each user action it finds; we collect those into a
list and return it.

Stage assignment happens later in Step 4.
"""

from __future__ import annotations

from pathlib import Path

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.tools.schema_tools import SchemaToolset
from skene.analyzers.schema_parsers.supabase_sql import parse_schema_dir
from skene.llm.base import LLMClient
from skene.output import status

SCHEMA_AGENT_INSTRUCTIONS = """\
You explore a parsed database schema and emit candidate user-journey
milestones. Be THOROUGH — err on the side of MORE milestones, not fewer.
A later step will deduplicate, classify, and discard noise. Your job is
recall.

A milestone is a meaningful user action with evidence in the schema. The
list below is suggestive, not exhaustive — emit a milestone for any table
that represents a user-facing capability:
- Signup / auth tables → "Account Created", "Email Verified"
- Workspace / organization / team tables → "Workspace Created", invites
- Settings / preferences / integration / api_key tables → onboarding
- Core domain tables (the ones that store the product's main objects:
  estimates, leads, chats, jobs, repos, documents, etc.) → activation +
  engagement (one milestone per *distinct* user-facing object type)
- Notification / email / digest tables → engagement
- Subscription / billing / plan / invoice / usage tables → expansion
- Referral / invite / share / public_link tables → virality
- Comment / reaction / collaboration / mention tables → engagement
- Export / import / report / webhook tables → expansion or engagement
- Audit / event / activity_log tables → may signal tracked user actions

Tools:
- list_schema_files: application schemas (internals hidden).
- list_tables(file): cheap per-table summary — column count, has_created_at,
  has_user_fk, pk_columns.
- describe_table(file, table): full columns, PK, FKs, indexes.
- search_tables(query): substring search across files.
- emit_milestone(...): record a milestone.

Process:
1. list_schema_files to see what's available.
2. list_tables for EVERY application file. Don't stop after one.
3. describe_table for every table that looks like a user-facing object,
   even if you're unsure — describing is cheap.
4. Call emit_milestone aggressively — every domain table likely deserves
   at least one milestone. A table that stores something a user creates,
   owns, or interacts with is almost always a milestone.

What to skip (only these):
- Pure join tables (composite PK of two FKs, no other columns).
- Internal queues, locks, and idempotency-key tables.
- Migration / schema-version metadata.

Rules:
- Do NOT classify into stages — that's a later step.
- Use lowercase snake_case for proposed_id.
- Set confidence < 0.8 when guessing from table name alone.
- Continue until you have examined every application table. Do not stop
  early — running out of obvious milestones is fine, but you must have
  looked at every table first.

When you have examined every application table and emitted every
milestone you can justify, reply with a brief plain-text summary (no
tool call) and stop.
"""


async def run_schema_agent(
    schema_dir: Path,
    llm: LLMClient,
    max_turns: int = 150,
) -> list[CandidateMilestone]:
    """Run the schema agent. Returns the list of emitted candidates."""
    status(f"Schema agent: parsing {schema_dir}")
    index = parse_schema_dir(schema_dir)
    table_count = sum(len(t) for t in index.files.values())
    status(
        f"Schema agent: parsed {len(index.files)} files, {table_count} tables "
        f"({len(index.application_files())} application)"
    )

    collector: list[CandidateMilestone] = []
    toolset = SchemaToolset(index, collector)
    tools = toolset.as_tools()

    status(f"Schema agent: starting LLM exploration (model={llm.get_model_name()} max_turns={max_turns})")
    result = await llm.run_agent(
        instructions=SCHEMA_AGENT_INSTRUCTIONS,
        tools=tools,
        initial_input="Begin exploring the schema. Emit one milestone per user action.",
        max_turns=max_turns,
    )
    status(
        f"Schema agent: emitted {len(collector)} candidate(s) (turns={result.turns}, stopped={result.stopped_reason})"
    )
    return collector
