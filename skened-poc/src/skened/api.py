"""FastAPI application exposing the daemon over a localhost REST API.

The future Tauri/web desktop shell consumes exactly these endpoints.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

_DASHBOARD = Path(__file__).parent / "web" / "index.html"

from . import __version__
from .comparison import ComparisonReport
from .config import Settings
from .journey import Journey
from .journey_pipeline import LlmAnalysisError
from .models import AnalysisRun, BranchInfo, Project
from .service import DaemonService, NotFoundError, ServiceError


class CreateProjectRequest(BaseModel):
    path: str
    name: str | None = None


class AnalyzeRequest(BaseModel):
    branch: str | None = None
    all: bool = False
    force: bool = False


class GoldFromBranchRequest(BaseModel):
    branch: str | None = None


class SettingsUpdate(BaseModel):
    analysis_backend: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_temperature: float | None = None
    monitor_enabled: bool | None = None
    monitor_interval: float | None = None
    monitor_on_commit: bool | None = None


def create_app(settings: Settings | None = None, service: DaemonService | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc = service or DaemonService(settings)
        app.state.service = svc
        await svc.start()
        try:
            yield
        finally:
            await svc.stop()

    app = FastAPI(title="skened", version=__version__, lifespan=lifespan)

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ServiceError)
    async def _bad_request(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(LlmAnalysisError)
    async def _llm_error(_: Request, exc: LlmAnalysisError) -> JSONResponse:
        # Synchronous analysis (e.g. gold-from-branch) surfaces LLM failures as 502.
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    def svc(request: Request) -> DaemonService:
        return request.app.state.service

    # --- dashboard -----------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return _DASHBOARD.read_text()

    # --- health --------------------------------------------------------------
    @app.get("/health")
    async def health(request: Request) -> dict:
        s = svc(request)
        return {
            "status": "ok",
            "version": __version__,
            "analysis": s.analysis_info(),
            "monitor": {
                "enabled": s.settings.monitor_enabled,
                "interval": s.settings.monitor_interval,
                "on_commit": s.settings.monitor_on_commit,
            },
        }

    # --- settings ------------------------------------------------------------
    @app.get("/settings")
    async def get_settings_route(request: Request) -> dict:
        return svc(request).settings_public()

    @app.patch("/settings")
    async def patch_settings(request: Request, body: SettingsUpdate) -> dict:
        return svc(request).update_settings(body.model_dump(exclude_unset=True))

    # --- projects ------------------------------------------------------------
    @app.get("/projects", response_model=list[Project])
    async def list_projects(request: Request):
        return svc(request).list_projects()

    @app.post("/projects", response_model=Project, status_code=201)
    async def create_project(request: Request, body: CreateProjectRequest):
        return await svc(request).add_project(body.path, body.name)

    @app.get("/projects/{project_id}", response_model=Project)
    async def get_project(request: Request, project_id: str):
        return svc(request).get_project(project_id)

    @app.delete("/projects/{project_id}", status_code=204)
    async def delete_project(request: Request, project_id: str):
        removed = svc(request).remove_project(project_id)
        if not removed:
            raise NotFoundError(f"project not found: {project_id}")
        return JSONResponse(status_code=204, content=None)

    # --- branches ------------------------------------------------------------
    @app.get("/projects/{project_id}/branches", response_model=list[BranchInfo])
    async def list_branches(request: Request, project_id: str):
        return await svc(request).list_branches(project_id)

    @app.get("/projects/{project_id}/branches/{branch:path}/journey")
    async def branch_journey(request: Request, project_id: str, branch: str):
        journey = await svc(request).get_branch_journey(project_id, branch)
        return JSONResponse(content=journey.model_dump(by_alias=True, mode="json"))

    # --- analysis ------------------------------------------------------------
    @app.post("/projects/{project_id}/analyze", response_model=list[AnalysisRun])
    async def analyze(request: Request, project_id: str, body: AnalyzeRequest):
        return await svc(request).enqueue_analysis(
            project_id, branch=body.branch, all_branches=body.all, force=body.force
        )

    @app.get("/projects/{project_id}/runs", response_model=list[AnalysisRun])
    async def list_runs(request: Request, project_id: str):
        return svc(request).list_runs(project_id)

    @app.get("/runs/{run_id}", response_model=AnalysisRun)
    async def get_run(request: Request, run_id: str):
        return svc(request).get_run(run_id)

    # --- comparison ----------------------------------------------------------
    @app.get("/projects/{project_id}/drift", response_model=ComparisonReport)
    async def project_drift(request: Request, project_id: str, base: str, head: str):
        return await svc(request).drift(project_id, base, head)

    @app.get("/projects/{project_id}/branches/{branch:path}/gap", response_model=ComparisonReport)
    async def branch_gap(request: Request, project_id: str, branch: str):
        return await svc(request).gap(project_id, branch)

    # --- gold standard -------------------------------------------------------
    @app.get("/projects/{project_id}/gold")
    async def get_gold(request: Request, project_id: str):
        journey = svc(request).get_gold(project_id)
        return JSONResponse(content=journey.model_dump(by_alias=True, mode="json"))

    @app.put("/projects/{project_id}/gold")
    async def set_gold(request: Request, project_id: str, journey: Journey):
        """Manually insert or edit the gold standard (full replacement)."""
        saved = svc(request).set_gold(project_id, journey)
        return JSONResponse(content=saved.model_dump(by_alias=True, mode="json"))

    @app.post("/projects/{project_id}/gold/from-branch")
    async def gold_from_branch(request: Request, project_id: str, body: GoldFromBranchRequest):
        journey = await svc(request).create_gold_from_branch(project_id, body.branch)
        return JSONResponse(content=journey.model_dump(by_alias=True, mode="json"))

    @app.delete("/projects/{project_id}/gold", status_code=204)
    async def delete_gold(request: Request, project_id: str):
        removed = svc(request).delete_gold(project_id)
        if not removed:
            raise NotFoundError(f"no gold standard set for project {project_id}")
        return JSONResponse(status_code=204, content=None)

    return app


# Module-level app for `uvicorn skened.api:app` / `python -m skened`.
app = create_app()
