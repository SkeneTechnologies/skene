"""Tests for the session service and run coordinator."""

from __future__ import annotations

import pytest

from skene.core.sessions import SessionBusyError
from skene.llm.agent_loop import ToolCall
from skene.schema import (
    AssistantMessage,
    PartCreated,
    PartUpdated,
    SessionCreated,
    TextPart,
    ToolPart,
    UserMessage,
)
from tests.fakes import HangingClient, ScriptedClient, turn


async def test_create_session_publishes_event(services, workspace):
    sub = services.bus.subscribe(workspace)
    session = await services.sessions.create_session(str(workspace), title="hello")
    assert session.agent == "skene"
    event = await sub.get(timeout=1)
    assert isinstance(event, SessionCreated)
    assert event.properties.session.id == session.id


async def test_prompt_runs_chat_to_idle(services, workspace):
    services.sessions.llm_factory = lambda: ScriptedClient(
        [
            turn(
                text="thinking",
                tool_calls=[ToolCall(id="c1", name="ghost", arguments={"x": 1})],
                usage={"input_tokens": 10, "output_tokens": 5},
            ),
            turn(text="done", usage={"input_tokens": 20, "output_tokens": 7}),
        ]
    )
    session = await services.sessions.create_session(str(workspace))
    sub = services.bus.subscribe(workspace)

    user_message = await services.sessions.prompt(session.id, "hi")
    assert isinstance(user_message, UserMessage)
    await services.sessions.wait(session.id)

    assert (await services.store.get_session(session.id)).status == "idle"

    messages = await services.store.list_messages(session.id)
    assert [type(m).__name__ for m, _ in messages] == ["UserMessage", "AssistantMessage"]
    assistant, parts = messages[1]
    assert isinstance(assistant, AssistantMessage)
    assert assistant.finish == "no_tool_calls"
    assert assistant.provider == "scripted"
    assert assistant.tokens.input == 30 and assistant.tokens.output == 12
    # thinking text, the (unknown) tool call, final text — in stream order.
    assert [type(p).__name__ for p in parts] == ["TextPart", "ToolPart", "TextPart"]
    tool_part = parts[1]
    assert isinstance(tool_part, ToolPart)
    assert tool_part.state.status == "error"  # unknown tool surfaces as tool error
    assert tool_part.state.input == {"x": 1}

    events = []
    while (event := await sub.get(timeout=0.05)) is not None:
        events.append(type(event).__name__)
    assert events[0] == "MessageCreated"  # the user message
    assert "PartUpdated" in events  # tool state transition
    assert events[-1] == "SessionIdle"


async def test_prompt_while_running_raises_busy(services, workspace):
    client = HangingClient()
    services.sessions.llm_factory = lambda: client
    session = await services.sessions.create_session(str(workspace))
    await services.sessions.prompt(session.id, "first")
    await client.called.wait()
    with pytest.raises(SessionBusyError):
        await services.sessions.prompt(session.id, "second")
    await services.sessions.abort(session.id)


async def test_abort_marks_run_aborted(services, workspace):
    client = HangingClient()
    services.sessions.llm_factory = lambda: client
    session = await services.sessions.create_session(str(workspace))
    await services.sessions.prompt(session.id, "hi")
    await client.called.wait()

    assert (await services.store.get_session(session.id)).status == "running"
    assert await services.sessions.abort(session.id) is True
    assert (await services.store.get_session(session.id)).status == "idle"
    assistant = (await services.store.list_messages(session.id))[-1][0]
    assert assistant.finish == "aborted"
    # A second abort is a no-op.
    assert await services.sessions.abort(session.id) is False


async def test_llm_failure_marks_session_error(services, workspace):
    def broken_factory():
        raise RuntimeError("no credentials")

    services.sessions.llm_factory = broken_factory
    session = await services.sessions.create_session(str(workspace))
    await services.sessions.prompt(session.id, "hi")
    await services.sessions.wait(session.id)

    assert (await services.store.get_session(session.id)).status == "error"
    assistant = (await services.store.list_messages(session.id))[-1][0]
    assert assistant.finish == "error"
    assert "no credentials" in assistant.error


async def test_user_prompt_text_is_dsn_redacted(services, workspace):
    services.sessions.llm_factory = lambda: ScriptedClient([turn(text="ok")])
    session = await services.sessions.create_session(str(workspace))
    await services.sessions.prompt(session.id, "analyse postgresql://user:secret@db:5432/app please")
    await services.sessions.wait(session.id)
    (_, user_parts), *_ = await services.store.list_messages(session.id)
    assert isinstance(user_parts[0], TextPart)
    assert "secret" not in user_parts[0].text
    assert "postgresql://user:***@db:5432/app" in user_parts[0].text


async def test_stream_events_are_scoped_to_directory(services, workspace, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    services.sessions.llm_factory = lambda: ScriptedClient([turn(text="ok")])
    session = await services.sessions.create_session(str(workspace))
    outsider = services.bus.subscribe(other)
    await services.sessions.prompt(session.id, "hi")
    await services.sessions.wait(session.id)
    assert await outsider.get(timeout=0.05) is None


async def test_resolve_llm_honours_model_override(services):
    calls = []

    def factory(model: str | None = None):
        calls.append(model)
        return ScriptedClient([turn(text="ok")])

    services.sessions.llm_factory = factory
    services.sessions.resolve_llm()
    services.sessions.resolve_llm("cheap-model")
    assert calls == [None, "cheap-model"]


async def test_resolve_llm_ignores_override_for_pinned_factory(services):
    client = ScriptedClient([turn(text="ok")])
    services.sessions.llm_factory = lambda: client
    assert services.sessions.resolve_llm("cheap-model") is client


def _event_names(events: list) -> list[str]:
    return [type(e).__name__ for e in events]


async def test_part_created_and_updated_shapes(services, workspace):
    services.sessions.llm_factory = lambda: ScriptedClient(
        [turn(tool_calls=[ToolCall(id="c1", name="ghost", arguments={})]), turn(text="done")]
    )
    session = await services.sessions.create_session(str(workspace))
    sub = services.bus.subscribe(workspace)
    await services.sessions.prompt(session.id, "go")
    await services.sessions.wait(session.id)

    created = []
    updated = []
    while (event := await sub.get(timeout=0.05)) is not None:
        if isinstance(event, PartCreated):
            created.append(event.properties.part)
        elif isinstance(event, PartUpdated):
            updated.append(event.properties.part)
    # ToolPart created running, then updated to a terminal state, same part id.
    tool_created = [p for p in created if isinstance(p, ToolPart)]
    tool_updated = [p for p in updated if isinstance(p, ToolPart)]
    assert len(tool_created) == 1 and len(tool_updated) == 1
    assert tool_created[0].id == tool_updated[0].id
    assert tool_created[0].state.status == "running"
    assert tool_updated[0].state.status == "error"
