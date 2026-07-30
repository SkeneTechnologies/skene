"""The journey analysis as a main-agent run (phase 3).

``analyse-journey`` is a *canned prompt* to a fresh ``skene`` session
(opencode's "command" concept): the main agent decides which subagents to
spawn through the ``task`` tool (child sessions, see
:mod:`skene.core.tasks`), then calls the ``synthesize_journey`` tool —
merge the feature map, synthesize milestones, assemble, serialize —
which reads the emitted features back from the child sessions' parts.

The phase-2 deterministic-pipeline wrapper this replaces was retired
after the parity check against ``tests/fixtures/parity`` passed. The
client contract is unchanged: ``POST /journey/analyse`` returns
``{sessionId}`` immediately, a finished run has an ``artifact`` part
pointing at ``journey.yaml``, and ``session.idle`` / ``session.error``
lands on the bus. These sessions now run as ``agent="skene"``.

Free-form prompts (``POST /session/{id}/message``) go through
:func:`make_run_factory`: a session whose agent is a registered primary
gets the same main-agent flow with workspace defaults (repo = the
workspace directory, no schema source); anything else falls back to the
tool-less chat run.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from skene.analyzers.journey.assemble import assemble_journey
from skene.analyzers.journey.feature_map import write_features
from skene.analyzers.journey.ground import ground_candidates
from skene.analyzers.journey.merge import merge_features_llm
from skene.analyzers.journey.models import Journey
from skene.analyzers.journey.serialize import write as write_journey
from skene.analyzers.journey.specialize import specialize_stages
from skene.analyzers.journey.stages import STAGES
from skene.analyzers.journey.synthesize import synthesize_milestones_llm
from skene.analyzers.schema_parsers.models import SchemaIndex
from skene.core.agents import AgentDef, AgentRegistry
from skene.core.permissions import PermissionService
from skene.core.redact import redact_db_url
from skene.core.sessions import RunFactory, SessionService
from skene.core.store import now_ms
from skene.core.tasks import build_task_tool
from skene.llm.agent_loop import Tool
from skene.llm.base import LLMClient
from skene.output import status
from skene.output_paths import DEFAULT_OUTPUT_DIR_NAME
from skene.schema import (
    ArtifactPart,
    AssistantMessage,
    Feature,
    FeaturePart,
    JourneyAnalyseRequest,
    Session,
    TextPart,
    UserMessage,
    new_id,
)


class JourneyRequestError(ValueError):
    """Invalid analyse request (bad paths / missing inputs)."""


class JourneyRunError(RuntimeError):
    """The main agent finished without producing the journey artifact."""


@dataclass
class JourneyRunConfig:
    """Resolved evidence sources and knobs for one main-agent run."""

    directory: str
    repo_root: Path | None
    schema_dir: Path | None
    db_url: str | None
    output: Path
    product_name: str
    classify_concurrency: int = 8
    schema_max_turns: int = 150
    code_max_turns: int = 200
    specialize: bool = True


class JourneyRunContext:
    """Shared state between the main-agent run and its tools.

    ``llm`` and ``message_id`` are filled in when the run starts (the
    tools close over the context, so they read both lazily); ``journey``
    is set by a successful ``synthesize_journey`` call.
    """

    def __init__(
        self,
        *,
        sessions: SessionService,
        registry: AgentRegistry,
        session: Session,
        config: JourneyRunConfig,
        llm: LLMClient | None = None,
        result: "asyncio.Future[Journey] | None" = None,
        permissions: PermissionService | None = None,
    ) -> None:
        self.sessions = sessions
        self.registry = registry
        self.session = session
        self.config = config
        self.llm = llm
        self.result = result
        # For tool closures that guard side effects behind an ask (none of
        # the built-in journey tools do yet — they are read-only).
        self.permissions = permissions
        self.message_id: str | None = None
        self.journey: Journey | None = None
        self._schema_index: SchemaIndex | None = None
        self._schema_lock = asyncio.Lock()

    async def schema_index(self) -> SchemaIndex:
        """The run's schema evidence, resolved once and cached.

        Parsing / live introspection are sync (sqlglot, psycopg), so both
        run off the event loop. ``db_url`` never leaves this method
        unredacted. Raises ``ValueError`` when the run has no schema
        source — the task tool surfaces that to the model as a tool error.
        """
        async with self._schema_lock:
            if self._schema_index is None:
                if self.config.schema_dir is not None:
                    from skene.analyzers.schema_parsers.supabase_sql import parse_schema_dir

                    status(f"Schema source: parsing {self.config.schema_dir}")
                    self._schema_index = await asyncio.to_thread(parse_schema_dir, self.config.schema_dir)
                elif self.config.db_url is not None:
                    from skene.analyzers.schema_parsers.postgres_live import introspect_db

                    status(f"Schema source: introspecting {redact_db_url(self.config.db_url)}")
                    self._schema_index = await asyncio.to_thread(introspect_db, self.config.db_url)
                else:
                    raise ValueError("no schema source configured for this run (need a schema dir or db url)")
            return self._schema_index


@dataclass
class JourneyRunHandle:
    """Returned by :func:`start_journey_run`.

    ``session`` identifies the run for HTTP clients; ``result`` resolves to
    the validated Journey for in-process callers (the embedded CLI).
    """

    session: Session
    result: "asyncio.Future[Journey]" = field(repr=False)


# ---------------------------------------------------------------------------
# Request resolution + the canned prompt
# ---------------------------------------------------------------------------


def _resolve_inputs(directory: str, request: JourneyAnalyseRequest) -> tuple[Path | None, Path | None, Path]:
    """Validate the request against the workspace; returns (repo, schema_dir, output)."""
    repo_root: Path | None = None
    if request.path is not None:
        repo_root = Path(request.path).expanduser().resolve()
    elif request.schema_dir is None and request.db_url is None:
        # Nothing specified at all: analyse the workspace directory itself.
        repo_root = Path(directory)
    if repo_root is not None and not repo_root.is_dir():
        raise JourneyRequestError(f"path is not a directory: {repo_root}")

    schema_dir: Path | None = None
    if request.schema_dir is not None:
        if request.db_url is not None:
            raise JourneyRequestError("schemaDir and dbUrl are mutually exclusive")
        schema_dir = Path(request.schema_dir).expanduser().resolve()
        if not schema_dir.is_dir():
            raise JourneyRequestError(f"schemaDir is not a directory: {schema_dir}")

    if request.output is not None:
        output = Path(request.output).expanduser().resolve()
    else:
        output = Path(directory) / DEFAULT_OUTPUT_DIR_NAME / "journey.yaml"
    return repo_root, schema_dir, output


def _config_from_request(
    directory: str, request: JourneyAnalyseRequest, repo_root: Path | None, schema_dir: Path | None, output: Path
) -> JourneyRunConfig:
    product_name = request.product_name or (repo_root or schema_dir or Path(directory)).name or "Product"
    return JourneyRunConfig(
        directory=directory,
        repo_root=repo_root,
        schema_dir=schema_dir,
        db_url=request.db_url,
        output=output,
        product_name=product_name,
        classify_concurrency=request.classify_concurrency,
        schema_max_turns=request.schema_max_turns,
        code_max_turns=request.code_max_turns,
        specialize=request.specialize,
    )


def _default_config(directory: str) -> JourneyRunConfig:
    """Workspace defaults for free-form prompts (no analyse request)."""
    return JourneyRunConfig(
        directory=directory,
        repo_root=Path(directory),
        schema_dir=None,
        db_url=None,
        output=Path(directory) / DEFAULT_OUTPUT_DIR_NAME / "journey.yaml",
        product_name=Path(directory).name or "Product",
    )


def _sources_display(config: JourneyRunConfig) -> str:
    """Human-readable list of the run's evidence sources.

    Shared by the canned prompt and the synthesis step (which uses it to
    judge journey coverage). Credentials never appear — the db url is
    described, not quoted.
    """
    if config.schema_dir is not None:
        schema_display = str(config.schema_dir)
    elif config.db_url is not None:
        schema_display = f"live database ({redact_db_url(config.db_url)})"
    else:
        schema_display = "(none)"
    return f"- Code repository: {config.repo_root or '(none)'}\n- Database schema: {schema_display}"


def canned_prompt(config: JourneyRunConfig) -> str:
    """The analyse-journey command as a prompt to the main agent.

    Also persisted verbatim as the session's user message, so the trace
    shows exactly what the agent was asked.
    """
    return (
        f"Analyse the user journey of {config.product_name}.\n\n"
        f"Evidence sources available:\n"
        f"{_sources_display(config)}\n\n"
        f"Output artifact: {config.output}\n\n"
        "Spawn the matching subagents with the task tool (all in one turn "
        "so they run in parallel), then call synthesize_journey, then "
        "reply with a short summary."
    )


# ---------------------------------------------------------------------------
# The synthesize_journey tool
# ---------------------------------------------------------------------------


def build_main_tools(ctx: JourneyRunContext) -> list[Tool]:
    return [build_task_tool(ctx), _build_synthesize_tool(ctx)]


def _build_synthesize_tool(ctx: JourneyRunContext) -> Tool:
    return Tool(
        name="synthesize_journey",
        description=(
            "Merge every feature emitted by this session's subagents into "
            "the deduplicated feature map (written as features.yaml), "
            "synthesize user-journey milestones from it, assemble the "
            "validated journey, and write the journey.yaml artifact. "
            "Returns a summary. Call after your task subagents finish."
        ),
        parameters={"type": "object", "properties": {}},
        handler=lambda args: _synthesize_journey(ctx),
    )


async def _collect_features(ctx: JourneyRunContext) -> tuple[list[Feature], list[Feature]]:
    """Features from the child sessions' parts, split schema/code."""
    schema_features: list[Feature] = []
    code_features: list[Feature] = []
    for child in await ctx.sessions.store.list_children(ctx.session.id):
        bucket = schema_features if child.agent == "schema" else code_features
        for _message, parts in await ctx.sessions.store.list_messages(child.id):
            bucket.extend(part.feature for part in parts if isinstance(part, FeaturePart))
    return schema_features, code_features


async def _synthesize_journey(ctx: JourneyRunContext) -> str:
    """The pipeline tail — merge the feature map, synthesize, assemble — as one tool."""
    schema_features, code_features = await _collect_features(ctx)
    if not schema_features and not code_features:
        raise ValueError("no features found — run task subagents first")

    stages = STAGES
    if ctx.config.specialize and ctx.config.repo_root is not None:
        stages = await specialize_stages(ctx.config.repo_root, ctx.config.product_name, llm=ctx.llm)

    status("synthesize: merging features (LLM grouping)")
    feature_map = await merge_features_llm(schema_features, code_features, llm=ctx.llm)
    status(
        f"synthesize: merged {len(schema_features)} schema + {len(code_features)} "
        f"code → {len(feature_map)} unique features"
    )

    output = ctx.config.output
    output.parent.mkdir(parents=True, exist_ok=True)
    features_output = output.parent / "features.yaml"
    write_features(feature_map, features_output, product_name=ctx.config.product_name)
    await ctx.sessions.emit_part(
        ArtifactPart(
            id=new_id("prt"),
            session_id=ctx.session.id,
            message_id=ctx.message_id or "",
            path=str(features_output),
            title="features.yaml",
            summary=f"Feature map: {len(feature_map)} features → {features_output}",
        )
    )

    status(f"synthesize: composing milestones from {len(feature_map)} features")
    candidates = await synthesize_milestones_llm(
        feature_map,
        llm=ctx.llm,
        stages=stages,
        classify_concurrency=ctx.config.classify_concurrency,
        sources=_sources_display(ctx.config),
    )
    known_tables: set[str] | None = None
    if ctx.config.schema_dir is not None or ctx.config.db_url is not None:
        index = await ctx.schema_index()
        known_tables = {t.name for tables in index.files.values() for t in tables}
    candidates, grounding = ground_candidates(candidates, repo_root=ctx.config.repo_root, known_tables=known_tables)
    if grounding.evidence_count or grounding.milestone_count:
        status(
            f"synthesize: grounding dropped {grounding.evidence_count} unverifiable "
            f"evidence chip(s) and {grounding.milestone_count} milestone(s) left without proof"
        )

    journey = assemble_journey(candidates, product_name=ctx.config.product_name, stages=stages)

    write_journey(journey, output)
    ctx.journey = journey

    milestone_count = sum(len(stage.milestones) for stage in journey.stages)
    summary = (
        f"Journey assembled: {len(journey.stages)} stages, {milestone_count} milestones "
        f"from {len(feature_map)} features → {output}"
    )
    status(f"synthesize: {summary}")
    await ctx.sessions.emit_part(
        ArtifactPart(
            id=new_id("prt"),
            session_id=ctx.session.id,
            message_id=ctx.message_id or "",
            path=str(output),
            title="journey.yaml",
            summary=summary,
        )
    )
    return summary


# ---------------------------------------------------------------------------
# The main-agent run
# ---------------------------------------------------------------------------


def make_run_factory(
    sessions: SessionService, registry: AgentRegistry, permissions: PermissionService | None = None
) -> RunFactory:
    """Prompt dispatch: primary agents get the main-agent flow with
    workspace defaults; everything else keeps the chat fallback."""

    def factory(session: Session, text: str):
        return _prompt_run(sessions, registry, permissions, session, text)

    return factory


async def _prompt_run(
    sessions: SessionService,
    registry: AgentRegistry,
    permissions: PermissionService | None,
    session: Session,
    text: str,
) -> None:
    agent = registry.get(session.agent)
    if agent is None or agent.mode != "primary":
        await sessions.chat_run(session, text)
        return
    directory = await sessions.store.session_directory(session.id)
    ctx = JourneyRunContext(
        sessions=sessions,
        registry=registry,
        session=session,
        config=_default_config(directory),
        permissions=permissions,
    )
    await _agent_run(ctx, agent, text)


async def _agent_run(ctx: JourneyRunContext, agent: AgentDef, initial_input: str) -> None:
    """Run the main agent to completion and settle ``ctx.result`` (if any)."""
    sessions = ctx.sessions

    def on_start(llm: LLMClient, message: AssistantMessage) -> None:
        ctx.llm = llm
        ctx.message_id = message.id

    try:
        await sessions.execute_run(
            ctx.session,
            instructions=agent.instructions,
            tools=build_main_tools(ctx),
            initial_input=initial_input,
            max_turns=agent.max_turns,
            llm=ctx.llm,
            model=agent.model,
            on_start=on_start,
        )
    except asyncio.CancelledError:
        if ctx.result is not None:
            ctx.result.cancel()
        raise
    except Exception as e:  # noqa: BLE001 — execute_run recorded it as session state
        if ctx.result is not None and not ctx.result.done():
            ctx.result.set_exception(e)
            # HTTP-triggered runs never await the handle; mark the exception
            # retrieved so the event loop doesn't log a GC warning for it.
            ctx.result.exception()
        return

    if ctx.result is None:
        # Free-form prompt: finishing without an artifact is fine.
        await sessions.set_status(ctx.session, "idle")
        return
    if ctx.journey is None:
        error = "main agent finished without calling synthesize_journey — no journey.yaml produced"
        await sessions.set_status(ctx.session, "error", error=error)
        ctx.result.set_exception(JourneyRunError(error))
        ctx.result.exception()
        return
    await sessions.set_status(ctx.session, "idle")
    ctx.result.set_result(ctx.journey)


async def start_journey_run(
    sessions: SessionService,
    registry: AgentRegistry,
    directory: str,
    request: JourneyAnalyseRequest,
    llm: LLMClient | None = None,
    permissions: PermissionService | None = None,
) -> JourneyRunHandle:
    """Create a ``skene`` session and send it the canned analyse prompt.

    Raises :class:`JourneyRequestError` before creating anything if the
    request is invalid. ``llm`` overrides the service's factory (the
    embedded CLI passes its already-configured client).
    """
    repo_root, schema_dir, output = _resolve_inputs(directory, request)
    config = _config_from_request(directory, request, repo_root, schema_dir, output)
    agent = registry.get("skene")
    if agent is None or agent.mode != "primary":
        raise JourneyRequestError("registry has no primary 'skene' agent")
    # Resolve before creating anything: no orphan session on missing credentials.
    llm = llm or sessions.resolve_llm(agent.model)

    session = await sessions.create_session(
        directory, agent=agent.name, title=f"analyse-journey: {config.product_name}"
    )
    prompt = canned_prompt(config)
    user_message = UserMessage(id=new_id("msg"), session_id=session.id, created=now_ms())
    await sessions.emit_message(user_message)
    await sessions.emit_part(TextPart(id=new_id("prt"), session_id=session.id, message_id=user_message.id, text=prompt))

    result: asyncio.Future[Journey] = asyncio.get_running_loop().create_future()
    ctx = JourneyRunContext(
        sessions=sessions,
        registry=registry,
        session=session,
        config=config,
        llm=llm,
        result=result,
        permissions=permissions,
    )
    sessions.start_run(session, _agent_run(ctx, agent, prompt))
    return JourneyRunHandle(session=session, result=result)
