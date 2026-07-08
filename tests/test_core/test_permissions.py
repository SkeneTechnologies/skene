"""Tests for the permission ask/answer flow."""

from __future__ import annotations

import asyncio

import pytest

from skene.core.permissions import PermissionAlreadyAnsweredError, UnknownPermissionError
from skene.schema import PermissionAnswered, PermissionAsked


async def _pending_request(services, workspace):
    """Start an ask in the background and return (task, asked event)."""
    session = await services.sessions.create_session(str(workspace))
    sub = services.bus.subscribe(workspace)
    task = asyncio.create_task(
        services.permissions.ask(
            session.id, tool="write_db", title="Write to table users?", metadata={"table": "users"}
        )
    )
    while True:
        event = await sub.get(timeout=1)
        assert event is not None, "no permission.asked event"
        if isinstance(event, PermissionAsked):
            return session, sub, task, event.properties.request


async def test_ask_allow_resumes_with_true(services, workspace):
    session, sub, task, request = await _pending_request(services, workspace)
    assert request.status == "pending"
    assert request.tool == "write_db"
    assert request.id.startswith("prm_")

    answered = await services.permissions.answer(request.id, "allow")
    assert answered.status == "allowed"
    assert answered.answered is not None
    assert await task is True

    # Answer persisted + published.
    stored = await services.store.get_permission(request.id)
    assert stored.status == "allowed"
    while (event := await sub.get(timeout=0.05)) is not None:
        if isinstance(event, PermissionAnswered):
            assert event.properties.request.status == "allowed"
            break
    else:
        pytest.fail("no permission.answered event")

    assert await services.store.list_permissions(session.id) == [stored]


async def test_ask_deny_resumes_with_false(services, workspace):
    _session, _sub, task, request = await _pending_request(services, workspace)
    await services.permissions.answer(request.id, "deny")
    assert await task is False
    assert (await services.store.get_permission(request.id)).status == "denied"


async def test_answer_unknown_and_already_answered(services, workspace):
    _session, _sub, task, request = await _pending_request(services, workspace)
    with pytest.raises(UnknownPermissionError):
        await services.permissions.answer("prm_nope", "allow")
    await services.permissions.answer(request.id, "allow")
    await task
    with pytest.raises(PermissionAlreadyAnsweredError):
        await services.permissions.answer(request.id, "deny")
    # The second answer did not overwrite the first.
    assert (await services.store.get_permission(request.id)).status == "allowed"


async def test_cancelled_ask_is_recorded_denied(services, workspace):
    _session, sub, task, request = await _pending_request(services, workspace)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await services.store.get_permission(request.id)).status == "denied"
    answered = None
    while (event := await sub.get(timeout=0.05)) is not None:
        if isinstance(event, PermissionAnswered):
            answered = event
    assert answered is not None, "cancellation must publish permission.answered"


async def test_answer_without_waiter_still_records(services, workspace):
    """A pending request whose waiter is gone (server restart) is still answerable."""
    _session, _sub, task, request = await _pending_request(services, workspace)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # The cancel path answered it; simulate a fresh pending row instead.
    fresh = request.model_copy(update={"id": "prm_restarted", "status": "pending"})
    await services.store.save_permission(fresh)
    answered = await services.permissions.answer("prm_restarted", "allow")
    assert answered.status == "allowed"
