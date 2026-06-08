"""A minimal tool-use agent loop on top of ``LLMClient.chat``.

Mirrors the reference pipeline's agent loop: send the conversation + tool schemas, run any
tool calls the model returns, append their results, and repeat until the model stops calling
tools or ``max_turns`` is hit.
"""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from .llm import LLMClient

logger = logging.getLogger("skened.pipeline.agent")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict           # JSON schema for the arguments object
    handler: Callable[..., Any]  # called with keyword args parsed from the tool call


def _stringify(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, default=str)
    except (TypeError, ValueError):
        return str(result)


async def run_agent(
    llm: LLMClient,
    *,
    system: str,
    tools: list[Tool],
    initial_input: str,
    max_turns: int = 40,
) -> int:
    """Drive the agent until it stops calling tools or ``max_turns`` is reached.

    Returns the number of turns taken. Side effects (e.g. emitted milestones) happen in the
    tool handlers' own collectors.
    """
    schema = [
        {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
        for t in tools
    ]
    by_name = {t.name: t for t in tools}
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": initial_input},
    ]

    turns = 0
    while turns < max_turns:
        turns += 1
        turn = await llm.chat(messages, tools=schema)
        messages.append(turn.raw_message)
        if not turn.tool_calls:
            break
        for tc in turn.tool_calls:
            tool = by_name.get(tc.name)
            if tool is None:
                result: Any = {"error": f"unknown tool {tc.name!r}"}
            else:
                try:
                    res = tool.handler(**tc.arguments)
                    result = await res if inspect.isawaitable(res) else res
                except Exception as e:  # noqa: BLE001 — surface tool errors to the model so it can recover
                    logger.debug("tool %s raised: %s", tc.name, e)
                    result = {"error": str(e)}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": _stringify(result)})
    return turns
