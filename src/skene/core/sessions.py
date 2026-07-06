"""Session lifecycle and the run coordinator.

:class:`SessionService` owns the mapping from HTTP verbs to engine work:
it creates sessions, starts prompt runs as background tasks, and cancels
them on abort. The run coordinator (:meth:`SessionService.consume_stream`)
is the phase-1 contract made concrete — it drains
``LLMClient.run_agent_stream`` and turns loop events into persisted parts
plus bus events, keeping the agent loop itself free of storage/HTTP
concerns:

    TurnStarted + AssistantText  → TextPart
    ToolCallStarted              → ToolPart(state=running)
    ToolCallFinished             → ToolPart(state=completed | error)
    RunFinished                  → assistant message finish/tokens

Phase 2 prompt runs are tool-less (the agent registry and task tool are
phase 3); the coordinator is written against the stream shape, so phase 3
reuses it unchanged for subagent runs.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any

from skene.core.bus import Bus
from skene.core.redact import redact_dsn_in_text
from skene.core.store import Store, UnknownSessionError, now_ms
from skene.llm.agent_loop import (
    AgentRunResult,
    AgentStreamEvent,
    AssistantText,
    RunFinished,
    ToolCallFinished,
    ToolCallStarted,
)
from skene.llm.base import LLMClient
from skene.output import debug, warning
from skene.schema import (
    AssistantMessage,
    Message,
    MessageCreated,
    MessageUpdated,
    Part,
    PartCreated,
    PartUpdated,
    Session,
    SessionCreated,
    SessionError,
    SessionIdle,
    SessionUpdated,
    TextPart,
    TokenUsage,
    ToolPart,
    ToolStateCompleted,
    ToolStateError,
    ToolStateRunning,
    UserMessage,
    new_id,
)

# Phase 2 placeholder: prompt runs are plain chat. Phase 3 replaces this
# with the agent registry's per-agent instructions + task tool.
_CHAT_INSTRUCTIONS = (
    "You are skene, a product-led-growth analysis assistant. Answer the "
    "user's question directly and concisely. You have no tools available "
    "in this session."
)

LLMFactory = Callable[[], LLMClient]


class SessionBusyError(RuntimeError):
    """Raised when a prompt arrives while the session is already running."""


class _Run:
    def __init__(self, task: asyncio.Task[None], abort: asyncio.Event) -> None:
        self.task = task
        self.abort = abort


class SessionService:
    def __init__(self, store: Store, bus: Bus, llm_factory: LLMFactory) -> None:
        self.store = store
        self.bus = bus
        self.llm_factory = llm_factory
        self._runs: dict[str, _Run] = {}

    # -- creation / queries ---------------------------------------------------

    async def create_session(
        self,
        directory: str,
        *,
        agent: str = "skene",
        parent_id: str | None = None,
        title: str | None = None,
    ) -> Session:
        project = await self.store.ensure_project(directory)
        if parent_id is not None:
            await self.store.get_session(parent_id)  # raises UnknownSessionError
        session = await self.store.create_session(project_id=project.id, agent=agent, parent_id=parent_id, title=title)
        self.bus.publish(SessionCreated(properties={"session": session}), directory=project.directory)
        return session

    def is_running(self, session_id: str) -> bool:
        run = self._runs.get(session_id)
        return run is not None and not run.task.done()

    async def wait(self, session_id: str) -> None:
        """Block until the session's active run (if any) finishes."""
        run = self._runs.get(session_id)
        if run is not None:
            await asyncio.shield(run.task)

    # -- prompt ---------------------------------------------------------------

    async def prompt(self, session_id: str, text: str) -> UserMessage:
        """Record the user message and start the run; returns immediately."""
        session = await self.store.get_session(session_id)
        if self.is_running(session_id):
            raise SessionBusyError(session_id)

        user_message = UserMessage(id=new_id("msg"), session_id=session.id, created=now_ms())
        user_part = TextPart(
            id=new_id("prt"),
            session_id=session.id,
            message_id=user_message.id,
            text=redact_dsn_in_text(text),
        )
        await self.store.save_message(user_message)
        await self.store.save_part(user_part)
        directory = await self.store.session_directory(session.id)
        self.bus.publish(MessageCreated(properties={"message": user_message}), directory=directory)
        self.bus.publish(PartCreated(properties={"part": user_part}), directory=directory)

        self.start_run(session, self._chat_run(session, text))
        return user_message

    def start_run(self, session: Session, coro: Coroutine[Any, Any, None]) -> None:
        """Register ``coro`` as the session's active background run task."""
        abort = asyncio.Event()
        task = asyncio.create_task(coro, name=f"skene-run-{session.id}")
        run = _Run(task, abort)
        self._runs[session.id] = run

        def _cleanup(_task: asyncio.Task[None]) -> None:
            if self._runs.get(session.id) is run:
                del self._runs[session.id]

        task.add_done_callback(_cleanup)

    async def abort(self, session_id: str) -> bool:
        """Cooperatively stop, then cancel, the session's active run."""
        await self.store.get_session(session_id)  # raises UnknownSessionError
        run = self._runs.get(session_id)
        if run is None or run.task.done():
            return False
        # Set the cooperative flag first (the loop checks it between turns),
        # then cancel the task so in-flight provider calls don't linger.
        run.abort.set()
        run.task.cancel()
        try:
            await run.task
        except asyncio.CancelledError:
            pass
        return True

    def abort_event(self, session_id: str) -> asyncio.Event | None:
        run = self._runs.get(session_id)
        return run.abort if run is not None else None

    # -- run coordinator -------------------------------------------------------

    async def set_status(self, session: Session, status: str, *, error: str | None = None) -> Session:
        session = await self.store.update_session(session.model_copy(update={"status": status}))
        directory = await self.store.session_directory(session.id)
        if status == "running":
            self.bus.publish(SessionUpdated(properties={"session": session}), directory=directory)
        elif status == "error":
            self.bus.publish(SessionError(properties={"session": session, "error": error or ""}), directory=directory)
        else:
            self.bus.publish(SessionIdle(properties={"session": session}), directory=directory)
        return session

    async def emit_message(self, message: Message, *, update: bool = False) -> None:
        await self.store.save_message(message)
        directory = await self.store.session_directory(message.session_id)
        event_cls = MessageUpdated if update else MessageCreated
        self.bus.publish(event_cls(properties={"message": message}), directory=directory)

    async def emit_part(self, part: Part, *, update: bool = False, delta: str | None = None) -> None:
        await self.store.save_part(part)
        directory = await self.store.session_directory(part.session_id)
        event_cls = PartUpdated if update else PartCreated
        self.bus.publish(event_cls(properties={"part": part, "delta": delta}), directory=directory)

    async def consume_stream(
        self,
        session: Session,
        message: AssistantMessage,
        stream: AsyncGenerator[AgentStreamEvent, None],
    ) -> AgentRunResult:
        """Drain an agent stream into parts + events under ``message``.

        Returns the final :class:`AgentRunResult`. The caller owns session
        status transitions and the final message finish/usage update.
        """
        tool_parts: dict[str, ToolPart] = {}
        result: AgentRunResult | None = None
        async for event in stream:
            if isinstance(event, AssistantText):
                part = TextPart(id=new_id("prt"), session_id=session.id, message_id=message.id, text=event.text)
                await self.emit_part(part, delta=event.text)
            elif isinstance(event, ToolCallStarted):
                part = ToolPart(
                    id=new_id("prt"),
                    session_id=session.id,
                    message_id=message.id,
                    tool=event.call.name,
                    call_id=event.call.id,
                    state=ToolStateRunning(input=_redact_inputs(event.call.arguments), started=now_ms()),
                )
                tool_parts[event.call.id] = part
                await self.emit_part(part)
            elif isinstance(event, ToolCallFinished):
                part = tool_parts.get(event.call.id)
                if part is None:  # defensive: finish without start
                    warning(f"tool finish for unknown call {event.call.id}")
                    continue
                started = part.state.started if isinstance(part.state, ToolStateRunning) else None
                inputs = _redact_inputs(event.call.arguments)
                if event.error:
                    state: ToolStateCompleted | ToolStateError = ToolStateError(
                        input=inputs, error=event.result, started=started, ended=now_ms()
                    )
                else:
                    state = ToolStateCompleted(input=inputs, output=event.result, started=started, ended=now_ms())
                part = part.model_copy(update={"state": state})
                tool_parts[event.call.id] = part
                await self.emit_part(part, update=True)
            elif isinstance(event, RunFinished):
                result = event.result
        if result is None:  # run_agent_stream guarantees RunFinished; be safe anyway
            raise RuntimeError("agent stream ended without RunFinished")
        return result

    # -- the phase-2 chat run ---------------------------------------------------

    async def _chat_run(self, session: Session, text: str) -> None:
        message = AssistantMessage(id=new_id("msg"), session_id=session.id, created=now_ms(), agent=session.agent)
        try:
            session = await self.set_status(session, "running")
            llm = self.llm_factory()
            message = message.model_copy(update={"provider": llm.get_provider_name(), "model": llm.get_model_name()})
            await self.emit_message(message)
            abort = self.abort_event(session.id)
            result = await self.consume_stream(
                session,
                message,
                llm.run_agent_stream(instructions=_CHAT_INSTRUCTIONS, tools=[], initial_input=text, abort=abort),
            )
            usage = result.usage or {}
            message = message.model_copy(
                update={
                    "finish": result.stopped_reason,
                    "tokens": TokenUsage(input=usage.get("input_tokens", 0), output=usage.get("output_tokens", 0))
                    if result.usage
                    else None,
                }
            )
            await self.emit_message(message, update=True)
            await self.set_status(session, "idle")
        except asyncio.CancelledError:
            debug(f"run for session {session.id} cancelled")
            message = message.model_copy(update={"finish": "aborted"})
            await self.emit_message(message, update=True)
            await self.set_status(session, "idle")
            raise
        except Exception as e:  # noqa: BLE001 — surface run failures as session state
            warning(f"run for session {session.id} failed: {e}")
            message = message.model_copy(update={"finish": "error", "error": str(e)})
            await self.emit_message(message, update=True)
            await self.set_status(session, "error", error=str(e))


def _redact_inputs(arguments: dict) -> dict:
    """Redact DSN credentials in string values before tool inputs hit disk/wire."""
    return {k: redact_dsn_in_text(v) if isinstance(v, str) else v for k, v in arguments.items()}


__all__ = ["SessionBusyError", "SessionService", "UnknownSessionError"]
