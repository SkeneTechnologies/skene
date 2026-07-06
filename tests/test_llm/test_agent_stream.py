"""Tests for the streaming agent loop (run_agent_stream) and cancellation."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

from skene.llm.agent_loop import (
    AgentStreamEvent,
    AssistantText,
    AssistantTurn,
    Message,
    RunFinished,
    Tool,
    ToolCall,
    ToolCallFinished,
    ToolCallStarted,
    TurnStarted,
)
from skene.llm.base import LLMClient


class _ScriptedClient(LLMClient):
    """Returns a queued AssistantTurn on each generate_with_tools call."""

    def __init__(self, turns: list[AssistantTurn]) -> None:
        self._turns = list(turns)

    async def generate_content_with_usage(self, prompt: str) -> tuple[str, dict[str, int] | None]:
        raise NotImplementedError

    async def generate_content_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        if False:
            yield ""
        raise NotImplementedError

    def get_model_name(self) -> str:
        return "scripted"

    def get_provider_name(self) -> str:
        return "scripted"

    async def generate_with_tools(self, messages: list[Message], tools: list[Tool]) -> AssistantTurn:
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


async def _drain(stream: AsyncGenerator[AgentStreamEvent, None]) -> list[AgentStreamEvent]:
    return [event async for event in stream]


async def test_stream_event_sequence_for_tool_run():
    client = _ScriptedClient(
        [
            AssistantTurn(
                text="thinking",
                tool_calls=[
                    ToolCall(id="c1", name="echo", arguments={"text": "a"}),
                    ToolCall(id="c2", name="echo", arguments={"text": "b"}),
                ],
            ),
            AssistantTurn(text="done"),
        ]
    )
    events = await _drain(client.run_agent_stream(instructions="", tools=[_echo_tool()], initial_input="go"))

    assert [type(e).__name__ for e in events] == [
        "TurnStarted",
        "AssistantText",
        "ToolCallStarted",
        "ToolCallFinished",
        "ToolCallStarted",
        "ToolCallFinished",
        "TurnStarted",
        "AssistantText",
        "RunFinished",
    ]
    first_started = events[2]
    assert isinstance(first_started, ToolCallStarted)
    assert first_started.call.id == "c1"
    first_finished = events[3]
    assert isinstance(first_finished, ToolCallFinished)
    assert first_finished.result == "echo: a"
    assert first_finished.error is False
    text = events[1]
    assert isinstance(text, AssistantText)
    assert text.text == "thinking" and text.turn == 1
    finished = events[-1]
    assert isinstance(finished, RunFinished)
    assert finished.result.stopped_reason == "no_tool_calls"
    assert finished.result.final_text == "done"


async def test_stream_marks_tool_errors():
    def _bad() -> Tool:
        async def handler(args: dict[str, Any]) -> str:
            raise RuntimeError("boom")

        return Tool(name="bad", description="", parameters={"type": "object", "properties": {}}, handler=handler)

    client = _ScriptedClient(
        [
            AssistantTurn(tool_calls=[ToolCall(id="c1", name="bad", arguments={})]),
            AssistantTurn(tool_calls=[ToolCall(id="c2", name="ghost", arguments={})]),
            AssistantTurn(text="ok"),
        ]
    )
    events = await _drain(client.run_agent_stream(instructions="", tools=[_bad()], initial_input="go"))
    finishes = [e for e in events if isinstance(e, ToolCallFinished)]
    assert [f.error for f in finishes] == [True, True]
    assert "boom" in finishes[0].result
    assert "unknown tool" in finishes[1].result


async def test_abort_before_first_turn():
    abort = asyncio.Event()
    abort.set()
    client = _ScriptedClient([AssistantTurn(text="never called")])
    events = await _drain(
        client.run_agent_stream(instructions="", tools=[_echo_tool()], initial_input="go", abort=abort)
    )
    assert len(events) == 1
    finished = events[0]
    assert isinstance(finished, RunFinished)
    assert finished.result.stopped_reason == "aborted"
    assert finished.result.turns == 0
    # The scripted turn was never consumed: no LLM call happened.
    assert client._turns


async def test_abort_between_tool_calls():
    abort = asyncio.Event()

    def _tripwire() -> Tool:
        async def handler(args: dict[str, Any]) -> str:
            abort.set()  # abort while the first tool of the turn runs
            return "ran"

        return Tool(name="trip", description="", parameters={"type": "object", "properties": {}}, handler=handler)

    client = _ScriptedClient(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall(id="c1", name="trip", arguments={}),
                    ToolCall(id="c2", name="trip", arguments={}),
                ],
            ),
            AssistantTurn(text="unreachable"),
        ]
    )
    events = await _drain(
        client.run_agent_stream(instructions="", tools=[_tripwire()], initial_input="go", abort=abort)
    )
    # First call dispatched, second one never started.
    assert [type(e).__name__ for e in events] == [
        "TurnStarted",
        "ToolCallStarted",
        "ToolCallFinished",
        "RunFinished",
    ]
    finished = events[-1]
    assert isinstance(finished, RunFinished)
    assert finished.result.stopped_reason == "aborted"
    assert finished.result.turns == 1


async def test_stream_ends_with_run_finished_on_max_turns():
    client = _ScriptedClient(
        [AssistantTurn(tool_calls=[ToolCall(id=f"c{i}", name="echo", arguments={"text": str(i)})]) for i in range(5)]
    )
    events = await _drain(
        client.run_agent_stream(instructions="", tools=[_echo_tool()], initial_input="go", max_turns=2)
    )
    finished = events[-1]
    assert isinstance(finished, RunFinished)
    assert finished.result.stopped_reason == "max_turns"
    assert finished.result.turns == 2
    assert isinstance(events[0], TurnStarted)


async def test_run_agent_wrapper_matches_stream_result():
    def make_client() -> _ScriptedClient:
        return _ScriptedClient(
            [
                AssistantTurn(
                    text=None,
                    tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "x"})],
                    usage={"input_tokens": 10, "output_tokens": 5},
                ),
                AssistantTurn(text="done", usage={"input_tokens": 20, "output_tokens": 8}),
            ]
        )

    result = await make_client().run_agent(instructions="", tools=[_echo_tool()], initial_input="go")
    events = await _drain(make_client().run_agent_stream(instructions="", tools=[_echo_tool()], initial_input="go"))
    finished = events[-1]
    assert isinstance(finished, RunFinished)
    streamed = finished.result

    assert result.final_text == streamed.final_text == "done"
    assert result.stopped_reason == streamed.stopped_reason == "no_tool_calls"
    assert result.turns == streamed.turns == 2
    assert result.usage == streamed.usage == {"input_tokens": 30, "output_tokens": 13}
    assert [m.role for m in result.messages] == [m.role for m in streamed.messages]
