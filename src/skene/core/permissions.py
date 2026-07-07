"""The permission ask/answer flow (phase 5).

A tool handler that wants to do something guarded calls
:meth:`PermissionService.ask` and suspends until a client answers via
``POST /session/{id}/permissions/{permID}`` (``permission.asked`` /
``permission.answered`` land on the bus around it). Tools reach the
service the same way the task tool reaches ``SessionService`` — by
closure over the run context — so the agent loop stays permission-free.

Design choices, deliberate and minimal:

- No rulesets yet (the design doc's allow/deny rules are future work):
  every ask goes to the client.
- No timeout: an ask stays pending until answered or the run is aborted.
  Abort cancels the awaiting tool handler; the cancellation path records
  the request as denied so nothing dangles in the DB or in clients.
- One-shot answers: answering a non-pending request is a conflict.
"""

from __future__ import annotations

import asyncio
from typing import Any

from skene.core.bus import Bus
from skene.core.store import Store, UnknownPermissionError, now_ms
from skene.schema import (
    PermissionAnswered,
    PermissionAsked,
    PermissionReply,
    PermissionRequest,
    new_id,
)


class PermissionAlreadyAnsweredError(RuntimeError):
    """Raised when answering a request that is no longer pending."""


class PermissionService:
    def __init__(self, store: Store, bus: Bus) -> None:
        self.store = store
        self.bus = bus
        self._pending: dict[str, asyncio.Future[bool]] = {}

    async def ask(
        self,
        session_id: str,
        *,
        tool: str,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Ask the client for permission; True means allowed.

        Blocks until a client answers. When the surrounding run is
        aborted, the request is recorded as denied and the cancellation
        propagates to the caller.
        """
        directory = await self.store.session_directory(session_id)
        request = PermissionRequest(
            id=new_id("prm"),
            session_id=session_id,
            tool=tool,
            title=title,
            metadata=metadata or {},
            created=now_ms(),
        )
        await self.store.save_permission(request)
        self.bus.publish(PermissionAsked(properties={"request": request}), directory=directory)

        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._pending[request.id] = future
        try:
            return await future
        except asyncio.CancelledError:
            # Run aborted while waiting — resolve the request as denied so
            # clients drop the prompt. Shielded: a second cancel must not
            # strand the request half-answered.
            await asyncio.shield(self._record_answer(request, "deny", directory))
            raise
        finally:
            self._pending.pop(request.id, None)

    async def answer(self, perm_id: str, reply: PermissionReply) -> PermissionRequest:
        """Resolve a pending ask; the awaiting tool handler resumes.

        Raises :class:`UnknownPermissionError` for unknown ids and
        :class:`PermissionAlreadyAnsweredError` for non-pending requests.
        Answering an ask whose waiter is gone (e.g. after a server
        restart) still records the answer.
        """
        request = await self.store.get_permission(perm_id)
        if request.status != "pending":
            raise PermissionAlreadyAnsweredError(perm_id)
        directory = await self.store.session_directory(request.session_id)
        request = await self._record_answer(request, reply, directory)
        future = self._pending.get(perm_id)
        if future is not None and not future.done():
            future.set_result(reply == "allow")
        return request

    async def _record_answer(
        self, request: PermissionRequest, reply: PermissionReply, directory: str
    ) -> PermissionRequest:
        request = request.model_copy(
            update={"status": "allowed" if reply == "allow" else "denied", "answered": now_ms()}
        )
        await self.store.save_permission(request)
        self.bus.publish(PermissionAnswered(properties={"request": request}), directory=directory)
        return request


__all__ = ["PermissionAlreadyAnsweredError", "PermissionService", "UnknownPermissionError"]
