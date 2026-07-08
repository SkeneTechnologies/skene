"""The ``task`` tool: subagent runs as child sessions.

opencode's task-tool pattern, adapted: the main agent calls
``task(agent=..., prompt=...)``; the handler creates a child session
(``parent_id`` = the calling session), runs the subagent's own agent loop
inside it via the shared run coordinator, and returns a JSON summary to
the parent when the child finishes. Because the loop dispatches one
turn's tool calls concurrently, several ``task`` calls in a single turn
run their subagents in parallel — one child session each.

Milestones stream live: after every successful ``emit_milestone`` call
the freshly collected :class:`CandidateMilestone` objects are persisted
as ``MilestonePart`` rows in the *child* session (``finalize_journey``
reads them back from there).

Abort fan-out: a child run is an independent asyncio task, so when the
parent run is cancelled the handler's cancellation path aborts the child
tree before re-raising (``SessionService.abort`` additionally walks
children itself, so directly-aborted parents don't rely on this path
alone).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from skene.analyzers.journey.tools.fs_tools import FsToolset
from skene.analyzers.journey.tools.schema_tools import SchemaToolset
from skene.core.agents import AgentDef
from skene.core.redact import redact_dsn_in_text
from skene.core.sessions import SessionService
from skene.core.store import now_ms
from skene.llm.agent_loop import AgentStreamEvent, Tool, ToolCallFinished
from skene.output import status
from skene.schema import (
    AssistantMessage,
    CandidateMilestone,
    MilestonePart,
    Session,
    TextPart,
    UserMessage,
    new_id,
)

if TYPE_CHECKING:
    from skene.core.journey import JourneyRunContext


@dataclass
class SubagentOutcome:
    """What a finished subagent run reports back to the task tool."""

    session_id: str
    milestones: int
    turns: int
    stopped_reason: str
    summary: str | None


def build_task_tool(ctx: "JourneyRunContext") -> Tool:
    subagents = ctx.registry.subagents()
    catalog = "\n".join(f"- {a.name}: {a.description}" for a in subagents)
    return Tool(
        name="task",
        description=(
            "Spawn a subagent in a child session and wait for it to finish. "
            "Returns a JSON summary including how many candidate milestones "
            "it emitted. Make multiple task calls in ONE turn to run "
            "subagents in parallel.\nAvailable agents:\n" + catalog
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": [a.name for a in subagents],
                    "description": "Which subagent to run.",
                },
                "prompt": {
                    "type": "string",
                    "description": "Instructions / focus for the subagent.",
                },
                "title": {
                    "type": "string",
                    "description": "Short label for the child session.",
                },
            },
            "required": ["agent", "prompt"],
        },
        handler=lambda args: _run_task(ctx, args),
    )


async def _run_task(ctx: "JourneyRunContext", args: dict) -> str:
    name = str(args["agent"])
    agent = ctx.registry.get(name)
    if agent is None or agent.mode != "subagent":
        available = sorted(a.name for a in ctx.registry.subagents())
        raise ValueError(f"unknown subagent {name!r}; available: {available}")
    prompt = str(args.get("prompt") or "Begin exploring. Emit one milestone per user action.")
    title = str(args.get("title") or f"task: {name}")

    collector: list[CandidateMilestone] = []
    # Raises ValueError when the run has no matching evidence source; the
    # loop feeds that back to the model, which adapts (design: reacting to
    # a missing schema is the agentic part).
    tools = await _build_subagent_tools(ctx, name, collector)

    sessions = ctx.sessions
    child = await sessions.create_session(ctx.config.directory, agent=name, parent_id=ctx.session.id, title=title)
    user_message = UserMessage(id=new_id("msg"), session_id=child.id, created=now_ms())
    await sessions.emit_message(user_message)
    await sessions.emit_part(
        TextPart(
            id=new_id("prt"),
            session_id=child.id,
            message_id=user_message.id,
            text=redact_dsn_in_text(prompt),
        )
    )

    status(f"task: {name} subagent started (session {child.id}, max_turns={_max_turns(ctx, agent)})")
    outcome: asyncio.Future[SubagentOutcome] = asyncio.get_running_loop().create_future()
    # A subagent with its own model resolves a fresh client inside the run
    # (execute_run surfaces credential failures as session state); otherwise
    # it shares the parent's client.
    llm = None if agent.model is not None else ctx.llm
    sessions.start_run(child, _subagent_run(sessions, child, agent, llm, tools, collector, prompt, ctx, outcome))
    try:
        result = await outcome
    except asyncio.CancelledError:
        # The parent run is being aborted — take the child (and anything it
        # spawned) down with it. Shielded so a second cancel can't strand
        # the child mid-cleanup.
        await asyncio.shield(sessions.abort(child.id))
        raise
    status(f"task: {name} subagent finished — {result.milestones} milestone(s), turns={result.turns}")
    return json.dumps(
        {
            "sessionId": result.session_id,
            "agent": name,
            "milestonesEmitted": result.milestones,
            "turns": result.turns,
            "stoppedReason": result.stopped_reason,
            "summary": result.summary,
        }
    )


async def _build_subagent_tools(ctx: "JourneyRunContext", name: str, collector: list[CandidateMilestone]) -> list[Tool]:
    """Bind a subagent to its toolset using the run's evidence sources."""
    if name == "code":
        if ctx.config.repo_root is None:
            raise ValueError("no code repository configured for this run")
        return FsToolset(ctx.config.repo_root, collector).as_tools()
    if name == "schema":
        return SchemaToolset(await ctx.schema_index(), collector).as_tools()
    raise ValueError(f"no toolset bound for subagent {name!r}")


def _max_turns(ctx: "JourneyRunContext", agent: AgentDef) -> int:
    if agent.name == "code":
        return ctx.config.code_max_turns
    if agent.name == "schema":
        return ctx.config.schema_max_turns
    return agent.max_turns


async def _subagent_run(
    sessions: SessionService,
    child: Session,
    agent: AgentDef,
    llm,
    tools: list[Tool],
    collector: list[CandidateMilestone],
    prompt: str,
    ctx: "JourneyRunContext",
    outcome: "asyncio.Future[SubagentOutcome]",
) -> None:
    """The child session's background run; resolves ``outcome`` for the task tool."""

    def wrap(session: Session, message: AssistantMessage, stream: AsyncGenerator[AgentStreamEvent, None]):
        return _stream_milestones(sessions, session, message, stream, collector)

    try:
        result = await sessions.execute_run(
            child,
            instructions=agent.instructions,
            tools=tools,
            initial_input=prompt,
            max_turns=_max_turns(ctx, agent),
            llm=llm,
            model=agent.model,
            wrap_stream=wrap,
        )
        await sessions.set_status(child, "idle")
        outcome.set_result(
            SubagentOutcome(
                session_id=child.id,
                milestones=len(collector),
                turns=result.turns,
                stopped_reason=result.stopped_reason,
                summary=result.final_text,
            )
        )
    except asyncio.CancelledError:
        if not outcome.done():
            outcome.cancel()
        raise
    except Exception as e:  # noqa: BLE001 — surfaced to the parent as a tool error
        if not outcome.done():
            outcome.set_exception(e)
            outcome.exception()  # pre-retrieve: the awaiter may already be gone


async def _stream_milestones(
    sessions: SessionService,
    session: Session,
    message: AssistantMessage,
    stream: AsyncGenerator[AgentStreamEvent, None],
    collector: list[CandidateMilestone],
) -> AsyncGenerator[AgentStreamEvent, None]:
    """Pass-through that persists newly collected milestones as parts."""
    flushed = 0
    async for event in stream:
        if isinstance(event, ToolCallFinished) and event.call.name == "emit_milestone" and not event.error:
            while flushed < len(collector):
                milestone = collector[flushed]
                flushed += 1
                await sessions.emit_part(
                    MilestonePart(
                        id=new_id("prt"),
                        session_id=session.id,
                        message_id=message.id,
                        milestone=milestone,
                    )
                )
        yield event
