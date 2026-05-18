"""Provider-agnostic tool-use loop on top of :class:`LLMClient`.

This module defines:

- :class:`Tool` — what a tool looks like to the loop (name, description, JSON
  Schema for parameters, and an async Python handler).
- :class:`ToolCall` / :class:`AssistantTurn` / :class:`Message` — the
  normalized shapes that each provider must translate to/from its native
  API.
- :class:`AgentRunResult` — what the loop returns: the final assistant
  text, the full message history, and aggregate usage.
- :func:`run_agent` — the default loop. Providers can override
  :meth:`LLMClient.run_agent` if they need different semantics, but the
  default is shared.

Tools are run sequentially in the order the model emitted them. A handler
that raises has its exception caught and stringified back to the model as
the tool result, so the agent can recover. The loop stops when:

- The model returns an assistant turn with no tool calls, OR
- ``max_turns`` is reached (counted from 1 per LLM call).

We deliberately do NOT expose a "this tool terminates the loop" hook —
journeygen relies on the model deciding it has nothing more to do. The
agent's instructions are responsible for that decision.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
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
    stopped_reason: str  # "no_tool_calls" | "max_turns"
    usage: dict[str, int] | None = None


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


async def run_agent(
    client: Any,  # LLMClient — typed as Any to avoid circular import
    instructions: str,
    tools: list[Tool],
    initial_input: str,
    max_turns: int = 20,
) -> AgentRunResult:
    """Run the agent loop until the model stops calling tools.

    ``client`` must implement ``generate_with_tools(messages, tools)``. The
    handlers in ``tools`` are dispatched here; the client never sees them.
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

    for turn_idx in range(1, max_turns + 1):
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

        if not turn.tool_calls:
            debug(f"agent loop done after {turn_idx} turn(s): no tool calls")
            return AgentRunResult(
                final_text=turn.text,
                messages=messages,
                turns=turn_idx,
                stopped_reason="no_tool_calls",
                usage=agg_usage if seen_any_usage else None,
            )

        # Dispatch each tool call sequentially. Order matches what the model emitted.
        for tc in turn.tool_calls:
            tool = tools_by_name.get(tc.name)
            if tool is None:
                result_str = json.dumps({"error": f"unknown tool {tc.name!r}; available: {sorted(tools_by_name)}"})
                warning(f"agent called unknown tool {tc.name!r}")
            else:
                try:
                    result_str = await _invoke_handler(tool.handler, tc.arguments)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001 — tool errors are recoverable
                    warning(f"tool {tc.name} raised: {e}")
                    result_str = json.dumps({"error": f"{type(e).__name__}: {e}"})
            messages.append(
                Message(
                    role="tool",
                    content=result_str,
                    tool_call_id=tc.id,
                    name=tc.name,
                )
            )

    warning(f"agent loop hit max_turns={max_turns} without finishing")
    return AgentRunResult(
        final_text=None,
        messages=messages,
        turns=max_turns,
        stopped_reason="max_turns",
        usage=agg_usage if seen_any_usage else None,
    )
