"""The v1-compat journey routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

from skene.core.journey import JourneyRequestError, start_journey_run
from skene.output_paths import BUNDLE_DIR_NAMES
from skene.schema import JourneyAnalyseAccepted, JourneyAnalyseRequest
from skene.server.deps import Directory, Services

router = APIRouter(tags=["journey"])


@router.post("/journey/analyse", response_model=JourneyAnalyseAccepted, status_code=202)
async def analyse(body: JourneyAnalyseRequest, services: Services, directory: Directory) -> JourneyAnalyseAccepted:
    """Start the canned journey analysis in a fresh session.

    The run proceeds async: watch ``/event`` for progress; the result lands
    as an ``artifact`` part (and as ``journey.yaml`` in the workspace).
    """
    try:
        handle = await start_journey_run(services.sessions, directory, body)
    except JourneyRequestError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        # The llm_factory refused (no credentials): fail fast instead of
        # creating a session doomed to error.
        raise HTTPException(status_code=503, detail=str(e)) from e
    return JourneyAnalyseAccepted(session_id=handle.session.id)


@router.get("/journey")
async def get_journey(directory: Directory) -> dict[str, Any]:
    """Latest ``journey.yaml`` for the workspace, parsed to JSON."""
    for bundle in BUNDLE_DIR_NAMES:
        path = Path(directory) / bundle / "journey.yaml"
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            raise HTTPException(status_code=500, detail=f"unparseable journey.yaml at {path}")
    raise HTTPException(status_code=404, detail="no journey.yaml in this workspace — run /journey/analyse first")
