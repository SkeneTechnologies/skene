"""Round-trip tests for the SQLite store."""

from __future__ import annotations

import pytest

from skene.core.store import UnknownSessionError, now_ms
from skene.schema import (
    AssistantMessage,
    TextPart,
    ToolPart,
    ToolStateCompleted,
    UserMessage,
    new_id,
)


async def test_ensure_project_is_idempotent(services, workspace):
    first = await services.store.ensure_project(workspace)
    second = await services.store.ensure_project(workspace)
    assert first.id == second.id
    assert first.directory == str(workspace.resolve())
    assert first.name == workspace.name


async def test_session_crud(services, workspace):
    project = await services.store.ensure_project(workspace)
    session = await services.store.create_session(project_id=project.id, agent="skene", title="t")
    assert session.status == "idle"

    fetched = await services.store.get_session(session.id)
    assert fetched == session

    updated = await services.store.update_session(session.model_copy(update={"status": "running"}))
    assert updated.status == "running"
    assert updated.updated >= session.updated
    assert (await services.store.get_session(session.id)).status == "running"

    child = await services.store.create_session(project_id=project.id, agent="code", parent_id=session.id)
    assert [s.id for s in await services.store.list_children(session.id)] == [child.id]
    assert [s.id for s in await services.store.list_sessions(project_id=project.id)] == [session.id, child.id]
    assert await services.store.session_directory(session.id) == project.directory

    with pytest.raises(UnknownSessionError):
        await services.store.get_session("ses_nope")
    with pytest.raises(UnknownSessionError):
        await services.store.session_directory("ses_nope")


async def test_message_and_part_round_trip(services, workspace):
    project = await services.store.ensure_project(workspace)
    session = await services.store.create_session(project_id=project.id, agent="skene")

    user = UserMessage(id=new_id("msg"), session_id=session.id, created=now_ms())
    assistant = AssistantMessage(id=new_id("msg"), session_id=session.id, created=now_ms(), agent="skene")
    await services.store.save_message(user)
    await services.store.save_message(assistant)

    text = TextPart(id=new_id("prt"), session_id=session.id, message_id=user.id, text="hello")
    tool = ToolPart(
        id=new_id("prt"),
        session_id=session.id,
        message_id=assistant.id,
        tool="echo",
        call_id="c1",
        state=ToolStateCompleted(input={"text": "hi"}, output="hi"),
    )
    await services.store.save_part(text)
    await services.store.save_part(tool)

    messages = await services.store.list_messages(session.id)
    assert [(m.id, [p.id for p in parts]) for m, parts in messages] == [
        (user.id, [text.id]),
        (assistant.id, [tool.id]),
    ]
    # Discriminated unions reconstruct to the exact subtype.
    restored = messages[1][1][0]
    assert isinstance(restored, ToolPart)
    assert restored.state == ToolStateCompleted(input={"text": "hi"}, output="hi")

    # save_part is an upsert: state transitions rewrite the row.
    await services.store.save_part(tool.model_copy(update={"state": ToolStateCompleted(output="bye")}))
    messages = await services.store.list_messages(session.id)
    assert messages[1][1][0].state.output == "bye"


async def test_counts(services, workspace):
    project = await services.store.ensure_project(workspace)
    await services.store.create_session(project_id=project.id, agent="skene")
    counts = await services.store.counts()
    assert counts == {"project": 1, "session": 1, "message": 0, "part": 0}
