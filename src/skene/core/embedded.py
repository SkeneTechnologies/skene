"""In-process (no socket) entry points for CLI commands.

The CLI's ``analyse-journey`` is opencode's ``run`` verb: it builds the
same core services the HTTP server would and drives them directly, so a
CLI run produces the same persisted session trace as a served one.
"""

from __future__ import annotations

from pathlib import Path

from skene.analyzers.journey.models import Journey
from skene.core.journey import start_journey_run
from skene.core.services import create_services
from skene.llm.base import LLMClient
from skene.schema import JourneyAnalyseRequest


async def run_journey_embedded(
    request: JourneyAnalyseRequest,
    llm: LLMClient,
    *,
    directory: Path | str,
    db_path: Path | str | None = None,
) -> Journey:
    """Run the canned journey analysis in an embedded session; returns the Journey.

    Raises whatever the pipeline raised (the session records the error too).
    """
    services = await create_services(db_path, llm_factory=lambda: llm)
    try:
        handle = await start_journey_run(
            services.sessions, services.registry, str(directory), request, llm=llm, permissions=services.permissions
        )
        try:
            return await handle.result
        finally:
            # The future resolves at the tail of the run task; let the task
            # itself finish before the store goes away.
            await services.sessions.wait(handle.session.id)
    finally:
        await services.close()
