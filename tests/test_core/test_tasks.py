"""Tests for the task tool: child sessions, abort fan-out, source errors."""

from __future__ import annotations

import asyncio

import pytest

from skene.core.journey import JourneyRunError, start_journey_run
from skene.llm.agent_loop import Message, Tool, ToolCall
from skene.schema import AssistantMessage, JourneyAnalyseRequest, TextPart, ToolPart
from tests.fakes import JourneyFakeLLM, ScriptedClient, turn


class _HangingChildLLM(JourneyFakeLLM):
    """Main agent spawns subagents; the code subagent hangs forever."""

    def __init__(self) -> None:
        super().__init__()
        self.child_called = asyncio.Event()

    async def generate_with_tools(self, messages: list[Message], tools: list[Tool]):
        system = (messages[0].content or "") if messages else ""
        if "explore a codebase" in system:
            self.child_called.set()
            await asyncio.Event().wait()
        return await super().generate_with_tools(messages, tools)


async def test_abort_fans_out_to_child_sessions(services, workspace):
    llm = _HangingChildLLM()
    request = JourneyAnalyseRequest(path=str(workspace), specialize=False)
    handle = await start_journey_run(services.sessions, services.registry, str(workspace), request, llm=llm)
    await asyncio.wait_for(llm.child_called.wait(), timeout=5)

    children = await services.store.list_children(handle.session.id)
    code_child = next(c for c in children if c.agent == "code")
    assert services.sessions.is_running(code_child.id)

    assert await services.sessions.abort(handle.session.id) is True
    assert handle.result.cancelled()

    assert not services.sessions.is_running(handle.session.id)
    assert not services.sessions.is_running(code_child.id)
    assert (await services.store.get_session(handle.session.id)).status == "idle"
    assert (await services.store.get_session(code_child.id)).status == "idle"
    child_assistant = next(
        m for m, _ in await services.store.list_messages(code_child.id) if isinstance(m, AssistantMessage)
    )
    assert child_assistant.finish == "aborted"


async def test_task_reports_missing_schema_source_as_tool_error(services, workspace):
    main = ScriptedClient(
        [
            turn(tool_calls=[ToolCall(id="t1", name="task", arguments={"agent": "schema", "prompt": "go"})]),
            turn(text="no schema available, stopping"),
        ]
    )
    request = JourneyAnalyseRequest(path=str(workspace), specialize=False)
    handle = await start_journey_run(services.sessions, services.registry, str(workspace), request, llm=main)
    with pytest.raises(JourneyRunError):
        await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)

    _, parts = (await services.store.list_messages(handle.session.id))[-1]
    task_part = next(p for p in parts if isinstance(p, ToolPart) and p.tool == "task")
    assert task_part.state.status == "error"
    assert "no schema source configured" in task_part.state.error
    # The failed spawn never created a child session.
    assert await services.store.list_children(handle.session.id) == []


async def test_task_rejects_unknown_subagent(services, workspace):
    main = ScriptedClient(
        [
            turn(tool_calls=[ToolCall(id="t1", name="task", arguments={"agent": "ghost", "prompt": "go"})]),
            turn(text="ok"),
        ]
    )
    request = JourneyAnalyseRequest(path=str(workspace), specialize=False)
    handle = await start_journey_run(services.sessions, services.registry, str(workspace), request, llm=main)
    with pytest.raises(JourneyRunError):
        await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)

    _, parts = (await services.store.list_messages(handle.session.id))[-1]
    task_part = next(p for p in parts if isinstance(p, ToolPart) and p.tool == "task")
    assert task_part.state.status == "error"
    assert "unknown subagent" in task_part.state.error


async def test_prompt_on_unregistered_agent_falls_back_to_chat(services, workspace):
    services.sessions.llm_factory = lambda: ScriptedClient([turn(text="plain answer")])
    session = await services.sessions.create_session(str(workspace), agent="mystery")
    await services.sessions.prompt(session.id, "hello?")
    await services.sessions.wait(session.id)

    assert (await services.store.get_session(session.id)).status == "idle"
    assistant, parts = (await services.store.list_messages(session.id))[-1]
    assert assistant.finish == "no_tool_calls"
    assert isinstance(parts[0], TextPart) and parts[0].text == "plain answer"
