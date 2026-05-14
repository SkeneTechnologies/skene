"""Tests for the provider-agnostic agent loop."""

from __future__ import annotations

from typing import Any, AsyncGenerator

import pytest

from skene.llm.agent_loop import (
    AssistantTurn,
    Message,
    Tool,
    ToolCall,
    run_agent,
)
from skene.llm.base import LLMClient


class _ScriptedClient(LLMClient):
    """Returns a queued AssistantTurn on each generate_with_tools call.

    Records every (messages, tools) pair it was called with so tests can
    assert on the conversation history that the loop builds up.
    """

    def __init__(self, turns: list[AssistantTurn]) -> None:
        self._turns = list(turns)
        self.calls: list[tuple[list[Message], list[Tool]]] = []

    async def generate_content_with_usage(
        self, prompt: str
    ) -> tuple[str, dict[str, int] | None]:
        raise NotImplementedError

    async def generate_content_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        if False:
            yield ""
        raise NotImplementedError

    def get_model_name(self) -> str:
        return "scripted"

    def get_provider_name(self) -> str:
        return "scripted"

    async def generate_with_tools(
        self, messages: list[Message], tools: list[Tool]
    ) -> AssistantTurn:
        # Snapshot the inputs so the test can inspect them later.
        self.calls.append(([Message(**m.__dict__) for m in messages], list(tools)))
        if not self._turns:
            raise AssertionError("scripted client ran out of turns")
        return self._turns.pop(0)


def _echo_tool() -> Tool:
    async def handler(args: dict[str, Any]) -> str:
        return f"echo: {args.get('text', '')}"

    return Tool(
        name="echo",
        description="Echo back the text argument.",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=handler,
    )


def _emit_tool(collector: list[dict[str, Any]]) -> Tool:
    async def handler(args: dict[str, Any]) -> str:
        collector.append(args)
        return f"recorded {args.get('id')}"

    return Tool(
        name="emit",
        description="Append the args to the collector.",
        parameters={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
        handler=handler,
    )


def _raising_tool() -> Tool:
    async def handler(args: dict[str, Any]) -> str:
        raise RuntimeError("boom")

    return Tool(
        name="bad",
        description="Always raises.",
        parameters={"type": "object", "properties": {}},
        handler=handler,
    )


@pytest.mark.asyncio
async def test_loop_stops_when_model_returns_no_tool_calls():
    client = _ScriptedClient([AssistantTurn(text="all done")])
    result = await client.run_agent(
        instructions="be brief",
        tools=[_echo_tool()],
        initial_input="hi",
    )
    assert result.stopped_reason == "no_tool_calls"
    assert result.final_text == "all done"
    assert result.turns == 1
    # System + user + assistant
    assert [m.role for m in result.messages] == ["system", "user", "assistant"]


@pytest.mark.asyncio
async def test_loop_dispatches_tool_calls_and_feeds_results_back():
    collector: list[dict[str, Any]] = []
    client = _ScriptedClient(
        [
            AssistantTurn(
                text=None,
                tool_calls=[
                    ToolCall(id="c1", name="emit", arguments={"id": "first"}),
                    ToolCall(id="c2", name="emit", arguments={"id": "second"}),
                ],
            ),
            AssistantTurn(text="done"),
        ]
    )
    result = await client.run_agent(
        instructions="emit two items",
        tools=[_emit_tool(collector)],
        initial_input="go",
    )
    assert collector == [{"id": "first"}, {"id": "second"}]
    assert result.stopped_reason == "no_tool_calls"
    # system, user, assistant(tool_calls), tool, tool, assistant("done")
    roles = [m.role for m in result.messages]
    assert roles == ["system", "user", "assistant", "tool", "tool", "assistant"]
    # Second call must include tool messages
    second_messages, _ = client.calls[1]
    assert [m.role for m in second_messages[-3:]] == ["assistant", "tool", "tool"]


@pytest.mark.asyncio
async def test_loop_stops_at_max_turns():
    client = _ScriptedClient(
        [
            AssistantTurn(
                text=None,
                tool_calls=[ToolCall(id=f"c{i}", name="echo", arguments={"text": str(i)})],
            )
            for i in range(10)
        ]
    )
    result = await client.run_agent(
        instructions="loop forever",
        tools=[_echo_tool()],
        initial_input="go",
        max_turns=3,
    )
    assert result.stopped_reason == "max_turns"
    assert result.turns == 3


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_to_model():
    client = _ScriptedClient(
        [
            AssistantTurn(
                text=None,
                tool_calls=[ToolCall(id="c1", name="ghost", arguments={})],
            ),
            AssistantTurn(text="ok"),
        ]
    )
    result = await client.run_agent(
        instructions="ignore",
        tools=[_echo_tool()],
        initial_input="go",
    )
    tool_msg = next(m for m in result.messages if m.role == "tool")
    assert "unknown tool" in (tool_msg.content or "")
    assert result.stopped_reason == "no_tool_calls"


@pytest.mark.asyncio
async def test_tool_exception_is_caught_and_reported():
    client = _ScriptedClient(
        [
            AssistantTurn(
                text=None,
                tool_calls=[ToolCall(id="c1", name="bad", arguments={})],
            ),
            AssistantTurn(text="ok"),
        ]
    )
    result = await client.run_agent(
        instructions="ignore",
        tools=[_raising_tool()],
        initial_input="go",
    )
    tool_msg = next(m for m in result.messages if m.role == "tool")
    assert "boom" in (tool_msg.content or "")
    assert "RuntimeError" in (tool_msg.content or "")
    # Loop continued despite the exception
    assert result.stopped_reason == "no_tool_calls"


@pytest.mark.asyncio
async def test_duplicate_tool_names_rejected():
    client = _ScriptedClient([AssistantTurn(text="ok")])
    with pytest.raises(ValueError, match="duplicate tool names"):
        await client.run_agent(
            instructions="",
            tools=[_echo_tool(), _echo_tool()],
            initial_input="",
        )


@pytest.mark.asyncio
async def test_usage_is_aggregated_across_turns():
    client = _ScriptedClient(
        [
            AssistantTurn(
                text=None,
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "1"})],
                usage={"input_tokens": 10, "output_tokens": 5},
            ),
            AssistantTurn(
                text="done",
                usage={"input_tokens": 20, "output_tokens": 8},
            ),
        ]
    )
    result = await client.run_agent(
        instructions="",
        tools=[_echo_tool()],
        initial_input="",
    )
    assert result.usage == {"input_tokens": 30, "output_tokens": 13}


@pytest.mark.asyncio
async def test_default_run_agent_raises_when_tools_not_supported():
    class Bare(LLMClient):
        async def generate_content_with_usage(self, prompt):
            return ("", None)

        async def generate_content_stream(self, prompt):
            if False:
                yield ""

        def get_model_name(self):
            return "bare"

        def get_provider_name(self):
            return "bare"

    client = Bare()
    with pytest.raises(NotImplementedError, match="bare"):
        await client.run_agent(
            instructions="",
            tools=[_echo_tool()],
            initial_input="",
        )
