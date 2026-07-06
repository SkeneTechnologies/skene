"""Provider-agnostic tool-use loop on top of :class:`LLMClient`.

This module defines:

- :class:`Tool` — what a tool looks like to the loop (name, description, JSON
  Schema for parameters, and an async Python handler).
- :class:`ToolCall` / :class:`AssistantTurn` / :class:`Message` — the
  normalized shapes that each provider must translate to/from its native
  API.
- :class:`AgentRunResult` — what the loop returns: the final assistant
  text, the full message history, and aggregate usage.
- :func:`run_agent_stream` — the default loop, as an async generator that
  yields :data:`AgentStreamEvent` items (turn boundaries, assistant text,
  tool-call start/finish) while it runs, ending with :class:`RunFinished`.
  This is what the server's session runner consumes to persist parts and
  publish bus events.
- :func:`run_agent` — drains the stream and returns the final
  :class:`AgentRunResult`. Providers can override
  :meth:`LLMClient.run_agent` if they need different semantics, but the
  default is shared.

Tools are run sequentially in the order the model emitted them. A handler
that raises has its exception caught and stringified back to the model as
the tool result, so the agent can recover. The loop stops when:

- The model returns an assistant turn with no tool calls, OR
- ``max_turns`` is reached (counted from 1 per LLM call), OR
- the ``abort`` event is set (checked before each LLM call and before each
  tool dispatch — a cheap cooperative cancel; in-flight awaits are not
  interrupted, cancel the task for that).

We deliberately do NOT expose a "this tool terminates the loop" hook —
journeygen relies on the model deciding it has nothing more to do. The
agent's instructions are responsible for that decision.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from skene.output import debug, warning

ToolHandler = Callable[[dict[str, Any]], Awaitable[str] | str]


@dataclass
class Tool:
    """A function the model can call.

    ``parameters`` is a JSON Schema describing the argument object. Provider
    adapters pass it through verbatim — keep it OpenAI-compatible (the
    superset all three majors accept).
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler


@dataclass
class ToolCall:
    """A tool invocation the model produced in one turn.

    ``provider_extras`` lets adapters stash provider-native metadata that
    has to round-trip on replay (e.g. Gemini's ``thought_signature``).
    Other adapters ignore it.
    """

    id: str
    name: str
    arguments: dict[str, Any]
    provider_extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssistantTurn:
    """One assistant response from ``generate_with_tools``.

    A turn carries either text, tool calls, or both. The loop terminates
    when ``tool_calls`` is empty.
    """

    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] | None = None
    raw: Any = None  # Provider-native object, useful for round-tripping.


@dataclass
class Message:
    """One message in the agent conversation.

    Roles:
    - ``system``: instructions. Always first.
    - ``user``: input from the caller.
    - ``assistant``: model output. May carry ``tool_calls`` plus optional text.
    - ``tool``: result of a tool call. Carries ``tool_call_id`` and the
      stringified result as ``content``.

    Provider adapters translate this into their native format inside
    ``generate_with_tools``.
    """

    role: str
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class AgentRunResult:
    """Final result of an agent run."""

    final_text: str | None
    messages: list[Message]
    turns: int
    stopped_reason: str  # "no_tool_calls" | "max_turns" | "aborted"
    usage: dict[str, int] | None = None


# ---------------------------------------------------------------------------
# Stream events
# ---------------------------------------------------------------------------


@dataclass
class TurnStarted:
    """About to make LLM call number ``turn`` (1-based)."""

    turn: int


@dataclass
class AssistantText:
    """The model produced text this turn (may accompany tool calls)."""

    turn: int
    text: str


@dataclass
class ToolCallStarted:
    """About to dispatch a tool handler."""

    turn: int
    call: ToolCall


@dataclass
class ToolCallFinished:
    """A tool handler returned (or failed — ``error`` is True and ``result``
    is the stringified error the model will see)."""

    turn: int
    call: ToolCall
    result: str
    error: bool = False


@dataclass
class RunFinished:
    """Always the last event of a stream."""

    result: AgentRunResult


AgentStreamEvent = TurnStarted | AssistantText | ToolCallStarted | ToolCallFinished | RunFinished


async def _invoke_handler(handler: ToolHandler, arguments: dict[str, Any]) -> str:
    result = handler(arguments)
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, str):
        # Stringify dicts/lists/numbers so the LLM sees them as JSON.
        try:
            return json.dumps(result, default=str)
        except Exception:  # noqa: BLE001
            return str(result)
    return result


async def run_agent_stream(
    client: Any,  # LLMClient — typed as Any to avoid circular import
    instructions: str,
    tools: list[Tool],
    initial_input: str,
    max_turns: int = 20,
    abort: asyncio.Event | None = None,
) -> AsyncGenerator[AgentStreamEvent, None]:
    """Run the agent loop, yielding events as it goes.

    ``client`` must implement ``generate_with_tools(messages, tools)``. The
    handlers in ``tools`` are dispatched here; the client never sees them.

    The last event is always :class:`RunFinished`. When ``abort`` is set the
    run finishes with ``stopped_reason="aborted"``; the message history may
    then end on an assistant turn whose tool calls were never answered.
    """
    tools_by_name = {t.name: t for t in tools}
    if len(tools_by_name) != len(tools):
        raise ValueError("duplicate tool names in run_agent")

    messages: list[Message] = [
        Message(role="system", content=instructions),
        Message(role="user", content=initial_input),
    ]

    agg_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
    seen_any_usage = False

    def _finish(final_text: str | None, turns: int, stopped_reason: str) -> RunFinished:
        return RunFinished(
            AgentRunResult(
                final_text=final_text,
                messages=messages,
                turns=turns,
                stopped_reason=stopped_reason,
                usage=agg_usage if seen_any_usage else None,
            )
        )

    def _aborted() -> bool:
        return abort is not None and abort.is_set()

    for turn_idx in range(1, max_turns + 1):
        if _aborted():
            debug(f"agent loop aborted before turn {turn_idx}")
            yield _finish(None, turn_idx - 1, "aborted")
            return

        yield TurnStarted(turn_idx)
        turn: AssistantTurn = await client.generate_with_tools(messages, tools)

        if turn.usage:
            seen_any_usage = True
            for k in ("input_tokens", "output_tokens"):
                v = turn.usage.get(k)
                if isinstance(v, int):
                    agg_usage[k] += v

        # Always append the assistant message — it may carry text + tool_calls
        messages.append(
            Message(
                role="assistant",
                content=turn.text,
                tool_calls=list(turn.tool_calls),
            )
        )
        if turn.text:
            yield AssistantText(turn_idx, turn.text)

        if not turn.tool_calls:
            debug(f"agent loop done after {turn_idx} turn(s): no tool calls")
            yield _finish(turn.text, turn_idx, "no_tool_calls")
            return

        # Dispatch each tool call sequentially. Order matches what the model emitted.
        for tc in turn.tool_calls:
            if _aborted():
                debug(f"agent loop aborted during turn {turn_idx}")
                yield _finish(None, turn_idx, "aborted")
                return

            yield ToolCallStarted(turn_idx, tc)
            is_error = False
            tool = tools_by_name.get(tc.name)
            if tool is None:
                result_str = json.dumps({"error": f"unknown tool {tc.name!r}; available: {sorted(tools_by_name)}"})
                is_error = True
                warning(f"agent called unknown tool {tc.name!r}")
            else:
                try:
                    result_str = await _invoke_handler(tool.handler, tc.arguments)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001 — tool errors are recoverable
                    warning(f"tool {tc.name} raised: {e}")
                    result_str = json.dumps({"error": f"{type(e).__name__}: {e}"})
                    is_error = True
            yield ToolCallFinished(turn_idx, tc, result_str, error=is_error)
            messages.append(
                Message(
                    role="tool",
                    content=result_str,
                    tool_call_id=tc.id,
                    name=tc.name,
                )
            )

    warning(f"agent loop hit max_turns={max_turns} without finishing")
    yield _finish(None, max_turns, "max_turns")


async def run_agent(
    client: Any,  # LLMClient — typed as Any to avoid circular import
    instructions: str,
    tools: list[Tool],
    initial_input: str,
    max_turns: int = 20,
    abort: asyncio.Event | None = None,
) -> AgentRunResult:
    """Run the agent loop to completion and return only the final result.

    Convenience wrapper over :func:`run_agent_stream` for callers that don't
    need progress events (the batch CLI path, tests).
    """
    async for event in run_agent_stream(
        client,
        instructions=instructions,
        tools=tools,
        initial_input=initial_input,
        max_turns=max_turns,
        abort=abort,
    ):
        if isinstance(event, RunFinished):
            return event.result
    raise RuntimeError("agent stream ended without RunFinished")
