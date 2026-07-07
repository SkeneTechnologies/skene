"""Session CRUD, prompting, and abort."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from skene.core.permissions import PermissionAlreadyAnsweredError
from skene.core.sessions import SessionBusyError
from skene.core.store import UnknownPermissionError, UnknownSessionError
from skene.schema import (
    Message,
    MessageWithParts,
    PermissionAnswer,
    PermissionRequest,
    PromptRequest,
    Session,
    SessionCreateRequest,
)
from skene.server.deps import Directory, Services

router = APIRouter(tags=["session"])


@router.post("/session", response_model=Session, status_code=201)
async def create_session(body: SessionCreateRequest, services: Services, directory: Directory) -> Session:
    try:
        return await services.sessions.create_session(
            directory, agent=body.agent, parent_id=body.parent_id, title=body.title
        )
    except UnknownSessionError as e:
        raise HTTPException(status_code=404, detail=f"unknown parent session: {e.args[0]}") from e


@router.get("/session", response_model=list[Session])
async def list_sessions(services: Services, directory: Directory) -> list[Session]:
    project = await services.store.ensure_project(directory)
    return await services.store.list_sessions(project_id=project.id)


@router.get("/session/{session_id}", response_model=Session)
async def get_session(session_id: str, services: Services) -> Session:
    try:
        return await services.store.get_session(session_id)
    except UnknownSessionError as e:
        raise HTTPException(status_code=404, detail=f"unknown session: {session_id}") from e


@router.get("/session/{session_id}/children", response_model=list[Session])
async def list_children(session_id: str, services: Services) -> list[Session]:
    try:
        await services.store.get_session(session_id)
    except UnknownSessionError as e:
        raise HTTPException(status_code=404, detail=f"unknown session: {session_id}") from e
    return await services.store.list_children(session_id)


@router.get("/session/{session_id}/message", response_model=list[MessageWithParts])
async def list_messages(session_id: str, services: Services) -> list[MessageWithParts]:
    try:
        await services.store.get_session(session_id)
    except UnknownSessionError as e:
        raise HTTPException(status_code=404, detail=f"unknown session: {session_id}") from e
    messages = await services.store.list_messages(session_id)
    return [MessageWithParts(info=message, parts=parts) for message, parts in messages]


@router.post("/session/{session_id}/message", response_model=Message, status_code=202)
async def prompt(session_id: str, body: PromptRequest, services: Services) -> Message:
    """Record the user message and start the run; progress streams on ``/event``."""
    try:
        return await services.sessions.prompt(session_id, body.text)
    except UnknownSessionError as e:
        raise HTTPException(status_code=404, detail=f"unknown session: {session_id}") from e
    except SessionBusyError as e:
        raise HTTPException(status_code=409, detail="session already has a run in progress") from e


@router.post("/session/{session_id}/abort")
async def abort(session_id: str, services: Services) -> dict[str, bool]:
    try:
        aborted = await services.sessions.abort(session_id)
    except UnknownSessionError as e:
        raise HTTPException(status_code=404, detail=f"unknown session: {session_id}") from e
    return {"aborted": aborted}


@router.get("/session/{session_id}/permissions", response_model=list[PermissionRequest])
async def list_permissions(session_id: str, services: Services) -> list[PermissionRequest]:
    """Every permission request the session has raised, pending first-created first."""
    try:
        await services.store.get_session(session_id)
    except UnknownSessionError as e:
        raise HTTPException(status_code=404, detail=f"unknown session: {session_id}") from e
    return await services.store.list_permissions(session_id)


@router.post("/session/{session_id}/permissions/{perm_id}", response_model=PermissionRequest)
async def answer_permission(
    session_id: str, perm_id: str, body: PermissionAnswer, services: Services
) -> PermissionRequest:
    """Answer a pending ask; the paused tool handler resumes with the verdict."""
    try:
        request = await services.store.get_permission(perm_id)
    except UnknownPermissionError as e:
        raise HTTPException(status_code=404, detail=f"unknown permission request: {perm_id}") from e
    if request.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"permission request {perm_id} is not part of session {session_id}")
    try:
        return await services.permissions.answer(perm_id, body.reply)
    except PermissionAlreadyAnsweredError as e:
        raise HTTPException(status_code=409, detail=f"permission request already answered: {request.status}") from e
