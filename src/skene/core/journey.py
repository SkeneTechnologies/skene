"""The canned journey analysis, run inside a session.

Phase 2 keeps the deterministic pipeline exactly as it is
(:func:`skene.analyzers.journey.pipeline.run_journey_pipeline`) and wraps
one execution of it in a session so every run is persisted, streamable,
and abortable. The wrapper emits coarse-grained parts — one ``ToolPart``
for the pipeline, then milestone/artifact/summary parts from the result.
Phase 3 replaces this wrapper with the real main-agent flow (task tool +
child sessions), which is when progress becomes per-agent and per-tool.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from skene.analyzers.journey.models import Journey
from skene.analyzers.journey.pipeline import JourneyPipelineConfig, run_journey_pipeline
from skene.analyzers.journey.serialize import write as write_journey
from skene.core.redact import redact_db_url
from skene.core.sessions import SessionService
from skene.core.store import now_ms
from skene.llm.base import LLMClient
from skene.output import status
from skene.output_paths import DEFAULT_OUTPUT_DIR_NAME
from skene.schema import (
    ArtifactPart,
    AssistantMessage,
    JourneyAnalyseRequest,
    MilestonePart,
    Session,
    TextPart,
    ToolPart,
    ToolStateCompleted,
    ToolStateError,
    ToolStateRunning,
    UserMessage,
    new_id,
)

JOURNEY_AGENT = "journey"
_PIPELINE_TOOL = "journey_pipeline"


@dataclass
class JourneyRunHandle:
    """Returned by :func:`start_journey_run`.

    ``session`` identifies the run for HTTP clients; ``result`` resolves to
    the validated Journey for in-process callers (the embedded CLI).
    """

    session: Session
    result: "asyncio.Future[Journey]"


class JourneyRequestError(ValueError):
    """Invalid analyse request (bad paths / missing inputs)."""


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


def _describe_request(
    product_name: str, repo_root: Path | None, schema_dir: Path | None, db_url: str | None, output: Path
) -> str:
    schema_display = str(schema_dir) if schema_dir else (redact_db_url(db_url) if db_url else "(none)")
    return (
        f"Analyse the user journey of {product_name}.\n"
        f"Repo: {repo_root or '(none)'}\n"
        f"Schema: {schema_display}\n"
        f"Output: {output}"
    )


async def start_journey_run(
    sessions: SessionService,
    directory: str,
    request: JourneyAnalyseRequest,
    llm: LLMClient | None = None,
) -> JourneyRunHandle:
    """Create a session for the analysis and kick off the run.

    Raises :class:`JourneyRequestError` before creating anything if the
    request is invalid. ``llm`` overrides the service's factory (the
    embedded CLI passes its already-configured client).
    """
    repo_root, schema_dir, output = _resolve_inputs(directory, request)
    product_name = request.product_name or (repo_root or schema_dir or Path(directory)).name or "Product"
    llm = llm or sessions.llm_factory()  # resolve before creating anything: no orphan session on missing credentials

    session = await sessions.create_session(directory, agent=JOURNEY_AGENT, title=f"analyse-journey: {product_name}")
    user_message = UserMessage(id=new_id("msg"), session_id=session.id, created=now_ms())
    await sessions.emit_message(user_message)
    await sessions.emit_part(
        TextPart(
            id=new_id("prt"),
            session_id=session.id,
            message_id=user_message.id,
            text=_describe_request(product_name, repo_root, schema_dir, request.db_url, output),
        )
    )

    result: asyncio.Future[Journey] = asyncio.get_running_loop().create_future()
    sessions.start_run(
        session,
        _journey_run(
            sessions,
            session,
            request,
            llm,
            repo_root=repo_root,
            schema_dir=schema_dir,
            output=output,
            product_name=product_name,
            result=result,
        ),
    )
    return JourneyRunHandle(session=session, result=result)


async def _journey_run(
    sessions: SessionService,
    session: Session,
    request: JourneyAnalyseRequest,
    llm: LLMClient,
    *,
    repo_root: Path | None,
    schema_dir: Path | None,
    output: Path,
    product_name: str,
    result: "asyncio.Future[Journey]",
) -> None:
    message = AssistantMessage(
        id=new_id("msg"),
        session_id=session.id,
        created=now_ms(),
        agent=JOURNEY_AGENT,
        provider=llm.get_provider_name(),
        model=llm.get_model_name(),
    )
    tool_part = ToolPart(
        id=new_id("prt"),
        session_id=session.id,
        message_id=message.id,
        tool=_PIPELINE_TOOL,
        call_id=new_id("call"),
        state=ToolStateRunning(
            input={
                "repo": str(repo_root) if repo_root else None,
                "schemaDir": str(schema_dir) if schema_dir else None,
                "dbUrl": redact_db_url(request.db_url) if request.db_url else None,
                "productName": product_name,
            },
            title="journey pipeline",
            started=now_ms(),
        ),
    )
    try:
        session = await sessions.set_status(session, "running")
        await sessions.emit_message(message)
        await sessions.emit_part(tool_part)

        schema_index = None
        if request.db_url is not None:
            from skene.analyzers.schema_parsers.postgres_live import introspect_db

            status(f"Introspecting database: {redact_db_url(request.db_url)}")
            # Sync psycopg call inside the async server — keep it off the loop.
            schema_index = await asyncio.to_thread(introspect_db, request.db_url)
            status(f"Introspection complete: {sum(len(t) for t in schema_index.files.values())} tables found")

        cfg = JourneyPipelineConfig(
            repo_root=repo_root,
            schema_dir=schema_dir,
            schema_index=schema_index,
            product_name=product_name,
            classify_concurrency=request.classify_concurrency,
            schema_max_turns=request.schema_max_turns,
            code_max_turns=request.code_max_turns,
            specialize=request.specialize,
        )
        journey = await run_journey_pipeline(cfg, llm)

        output.parent.mkdir(parents=True, exist_ok=True)
        write_journey(journey, output)

        milestone_count = 0
        for stage in journey.stages:
            for milestone in stage.milestones:
                milestone_count += 1
                await sessions.emit_part(
                    MilestonePart(
                        id=new_id("prt"),
                        session_id=session.id,
                        message_id=message.id,
                        milestone={"stage_id": stage.id, **milestone.model_dump(mode="json")},
                    )
                )
        summary = f"Journey assembled: {len(journey.stages)} stages, {milestone_count} milestones."
        await sessions.emit_part(
            tool_part.model_copy(
                update={
                    "state": ToolStateCompleted(
                        input=tool_part.state.input,
                        output=summary,
                        title="journey pipeline",
                        started=tool_part.state.started,
                        ended=now_ms(),
                    )
                }
            ),
            update=True,
        )
        await sessions.emit_part(
            ArtifactPart(
                id=new_id("prt"),
                session_id=session.id,
                message_id=message.id,
                path=str(output),
                title="journey.yaml",
                summary=summary,
            )
        )
        await sessions.emit_part(TextPart(id=new_id("prt"), session_id=session.id, message_id=message.id, text=summary))
        await sessions.emit_message(message.model_copy(update={"finish": "completed"}), update=True)
        await sessions.set_status(session, "idle")
        result.set_result(journey)
    except asyncio.CancelledError:
        await sessions.emit_part(
            tool_part.model_copy(
                update={
                    "state": ToolStateError(
                        input=tool_part.state.input,
                        error="aborted",
                        started=tool_part.state.started,
                        ended=now_ms(),
                    )
                }
            ),
            update=True,
        )
        await sessions.emit_message(message.model_copy(update={"finish": "aborted"}), update=True)
        await sessions.set_status(session, "idle")
        result.cancel()
        raise
    except Exception as e:  # noqa: BLE001 — surface pipeline failures as session state
        await sessions.emit_part(
            tool_part.model_copy(
                update={
                    "state": ToolStateError(
                        input=tool_part.state.input,
                        error=str(e),
                        started=tool_part.state.started,
                        ended=now_ms(),
                    )
                }
            ),
            update=True,
        )
        await sessions.emit_message(message.model_copy(update={"finish": "error", "error": str(e)}), update=True)
        await sessions.set_status(session, "error", error=str(e))
        result.set_exception(e)
        # HTTP-triggered runs never await the handle; mark the exception
        # retrieved so the event loop doesn't log a GC warning for it.
        result.exception()
