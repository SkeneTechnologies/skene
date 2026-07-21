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

:meth:`SessionService.execute_run` layers the standard run bookkeeping
(assistant message, status transitions, abort/error recording) on top of
the coordinator; every kind of run — plain chat fallback, the main skene
agent, task-tool subagents — goes through it.

Prompt runs are dispatched through :attr:`SessionService.run_factory`
(wired by :func:`skene.core.services.create_services` to the agent
registry's main-agent flow); without a factory they fall back to the
tool-less chat run.
"""

from __future__ import annotations

import asyncio
import inspect
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
    Tool,
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

# Fallback for sessions whose agent isn't a registered primary agent
# (no run_factory wired, or an unknown agent name).
_CHAT_INSTRUCTIONS = (
    "You are skene, a product-led-growth analysis assistant. Answer the "
    "user's question directly and concisely. You have no tools available "
    "in this session."
)

# Called with no arguments for the default client; a factory that also
# accepts a ``model`` keyword opts in to per-agent overrides (AgentDef.model).
LLMFactory = Callable[..., LLMClient]

# Builds the background run for a prompt; see skene.core.journey.make_run_factory.
RunFactory = Callable[["Session", str], Coroutine[Any, Any, None]]

# Optional per-run stream decorator (e.g. milestone-part flushing in tasks.py).
StreamWrapper = Callable[
    ["Session", "AssistantMessage", AsyncGenerator[AgentStreamEvent, None]],
    AsyncGenerator[AgentStreamEvent, None],
]


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
        # Wired post-construction (skene.core.services) to avoid a circular
        # import; None keeps the chat fallback for bare service setups.
        self.run_factory: RunFactory | None = None
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

        run = self.run_factory(session, text) if self.run_factory is not None else self.chat_run(session, text)
        self.start_run(session, run)
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
        """Cooperatively stop, then cancel, the session's run tree.

        Child-session runs (task-tool subagents) are independent asyncio
        tasks, so the whole descendant tree is walked: parent first — its
        cancellation path already aborts the children it is waiting on —
        then every stored child, to catch runs the parent had let go of.
        """
        await self.store.get_session(session_id)  # raises UnknownSessionError
        return await self._abort_tree(session_id)

    async def _abort_tree(self, session_id: str) -> bool:
        aborted = await self._abort_run(session_id)
        for child in await self.store.list_children(session_id):
            aborted = (await self._abort_tree(child.id)) or aborted
        return aborted

    async def _abort_run(self, session_id: str) -> bool:
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

    # -- LLM resolution ---------------------------------------------------------

    def resolve_llm(self, model: str | None = None) -> LLMClient:
        """A client from the service factory, honouring a per-agent model.

        Overrides need a factory that accepts ``model`` (``skene serve``
        wires one); with a zero-arg factory (tests, the embedded CLI's
        pinned client) the override is ignored with a debug note.
        """
        if model is None:
            return self.llm_factory()
        try:
            accepts_model = "model" in inspect.signature(self.llm_factory).parameters
        except (TypeError, ValueError):
            accepts_model = False
        if accepts_model:
            return self.llm_factory(model=model)
        debug(f"llm factory does not accept model overrides; ignoring model={model!r}")
        return self.llm_factory()

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
                    state=_running_state(event.call.name, event.call.arguments),
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
                    state = ToolStateCompleted(
                        input=inputs,
                        output=event.result,
                        title=_tool_title(event.call.name, inputs),
                        started=started,
                        ended=now_ms(),
                    )
                part = part.model_copy(update={"state": state})
                tool_parts[event.call.id] = part
                await self.emit_part(part, update=True)
            elif isinstance(event, RunFinished):
                result = event.result
        if result is None:  # run_agent_stream guarantees RunFinished; be safe anyway
            raise RuntimeError("agent stream ended without RunFinished")
        return result

    # -- standard run bookkeeping ------------------------------------------------

    async def execute_run(
        self,
        session: Session,
        *,
        instructions: str,
        tools: list[Tool],
        initial_input: str,
        max_turns: int = 20,
        llm: LLMClient | None = None,
        model: str | None = None,
        wrap_stream: StreamWrapper | None = None,
        on_start: Callable[[LLMClient, AssistantMessage], None] | None = None,
    ) -> AgentRunResult:
        """Run one agent loop under ``session`` with standard bookkeeping.

        Owns the assistant message and the running/aborted/error recording.
        On success the session is left ``running`` and the result returned —
        the caller decides the terminal status (usually ``idle``, but the
        canned journey run turns a missing artifact into ``error``).
        Cancellation and failures are recorded as session state, then
        re-raised for the caller's own cleanup (futures, child aborts).

        ``llm`` defaults to the service factory (resolved inside the run so
        credential failures surface as session errors), with ``model`` as
        the per-agent override passed to :meth:`resolve_llm`; ``on_start``
        fires after the assistant message exists, with the resolved client.
        """
        message = AssistantMessage(id=new_id("msg"), session_id=session.id, created=now_ms(), agent=session.agent)
        try:
            session = await self.set_status(session, "running")
            llm = llm if llm is not None else self.resolve_llm(model)
            message = message.model_copy(update={"provider": llm.get_provider_name(), "model": llm.get_model_name()})
            await self.emit_message(message)
            if on_start is not None:
                on_start(llm, message)
            abort = self.abort_event(session.id)
            stream = llm.run_agent_stream(
                instructions=instructions,
                tools=tools,
                initial_input=initial_input,
                max_turns=max_turns,
                abort=abort,
            )
            if wrap_stream is not None:
                stream = wrap_stream(session, message, stream)
            result = await self.consume_stream(session, message, stream)
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
            return result
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
            raise

    # -- the tool-less chat fallback ---------------------------------------------

    async def chat_run(self, session: Session, text: str) -> None:
        try:
            await self.execute_run(session, instructions=_CHAT_INSTRUCTIONS, tools=[], initial_input=text)
            await self.set_status(session, "idle")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001, S110 — already recorded as session state
            pass


def _redact_inputs(arguments: dict) -> dict:
    """Redact DSN credentials in string values before tool inputs hit disk/wire."""
    return {k: redact_dsn_in_text(v) if isinstance(v, str) else v for k, v in arguments.items()}


def _running_state(tool_name: str, arguments: dict) -> ToolStateRunning:
    inputs = _redact_inputs(arguments)
    return ToolStateRunning(input=inputs, title=_tool_title(tool_name, inputs), started=now_ms())


# Argument keys worth surfacing in a tool title, most descriptive first:
# the feature being emitted, the search pattern/query, the table or file
# being inspected, the schema file, the subagent being spawned. `pattern`
# outranks `path` because search_files sends both (path is usually ".").
_TITLE_KEYS = ("name", "pattern", "query", "table", "path", "schema_file", "agent")

_TITLE_VALUE_MAX = 60


def _tool_title(tool_name: str, inputs: dict) -> str | None:
    """Short human title for a tool call, e.g. ``read_file app/page.tsx``.

    Clients render it in place of the bare tool name so progress lines say
    *what* is being inspected. Built from the already-redacted inputs;
    None (no recognizable argument) keeps the bare tool name.
    """
    for key in _TITLE_KEYS:
        value = inputs.get(key)
        if isinstance(value, str) and value.strip():
            value = " ".join(value.split())
            if len(value) > _TITLE_VALUE_MAX:
                value = value[:_TITLE_VALUE_MAX] + "…"
            return f"{tool_name} {value}"
    return None


__all__ = ["SessionBusyError", "SessionService", "UnknownSessionError"]
