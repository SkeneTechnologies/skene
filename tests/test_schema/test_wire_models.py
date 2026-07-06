"""Tests for the wire-format models in skene.schema."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from skene.schema import (
    AssistantMessage,
    Event,
    Message,
    Part,
    PartUpdated,
    Session,
    SessionCreated,
    TextPart,
    TokenUsage,
    ToolPart,
    ToolStateCompleted,
    ToolStateRunning,
    UserMessage,
    new_id,
)

PART = TypeAdapter(Part)
MESSAGE = TypeAdapter(Message)
EVENT = TypeAdapter(Event)


def _session() -> Session:
    return Session(
        id=new_id("ses"),
        project_id=new_id("prj"),
        agent="skene",
        created=1000,
        updated=1000,
    )


def test_ids_are_prefixed_and_time_sortable():
    first = new_id("ses")
    second = new_id("ses")
    assert first.startswith("ses_")
    assert first != second
    assert sorted([second, first]) == [first, second]


def test_wire_json_is_camel_case_and_round_trips():
    msg = AssistantMessage(
        id=new_id("msg"),
        session_id="ses_1",
        created=1000,
        agent="skene",
        tokens=TokenUsage(input=10, output=5),
    )
    data = msg.model_dump(mode="json")
    assert "sessionId" in data and "session_id" not in data

    # Round-trip through the discriminated union.
    back = MESSAGE.validate_python(data)
    assert isinstance(back, AssistantMessage)
    assert back == msg


def test_message_union_discriminates_on_role():
    user = MESSAGE.validate_python({"id": "msg_1", "sessionId": "ses_1", "created": 1, "role": "user"})
    assert isinstance(user, UserMessage)
    with pytest.raises(ValidationError):
        MESSAGE.validate_python({"id": "msg_1", "sessionId": "ses_1", "created": 1, "role": "alien"})


def test_part_union_discriminates_on_type():
    raw = {
        "id": "prt_1",
        "sessionId": "ses_1",
        "messageId": "msg_1",
        "type": "tool",
        "tool": "read_file",
        "callId": "c1",
        "state": {"status": "running", "input": {"path": "x"}, "started": 123},
    }
    part = PART.validate_python(raw)
    assert isinstance(part, ToolPart)
    assert isinstance(part.state, ToolStateRunning)

    done = part.model_copy(
        update={"state": ToolStateCompleted(input={"path": "x"}, output="ok", started=123, ended=456)}
    )
    assert isinstance(done.state, ToolStateCompleted)


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        TextPart(
            id="prt_1",
            session_id="ses_1",
            message_id="msg_1",
            text="hi",
            surprise="nope",  # type: ignore[call-arg]
        )


def test_event_envelope_shape_and_union():
    event = SessionCreated(properties={"session": _session()})
    data = event.model_dump(mode="json")
    # opencode SSE wire shape: {id, type, properties}
    assert set(data) == {"id", "type", "properties"}
    assert data["type"] == "session.created"
    assert data["id"].startswith("evt_")

    back = EVENT.validate_python(data)
    assert isinstance(back, SessionCreated)


def test_part_updated_carries_streaming_delta():
    part = TextPart(id="prt_1", session_id="ses_1", message_id="msg_1", text="hello wo")
    event = PartUpdated(properties={"part": part, "delta": " wo"})
    data = event.model_dump(mode="json")
    assert data["properties"]["delta"] == " wo"
    assert data["properties"]["part"]["type"] == "text"
