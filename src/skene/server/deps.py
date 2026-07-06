"""Shared FastAPI dependencies: services access, workspace routing, auth."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from skene.core.bus import normalize_directory
from skene.core.services import CoreServices

DIRECTORY_HEADER = "x-skene-directory"


def get_services(request: Request) -> CoreServices:
    return request.app.state.services


def workspace_directory(
    x_skene_directory: Annotated[str | None, Header()] = None,
) -> str:
    """Workspace a request operates on (opencode's per-request routing).

    Falls back to the server's working directory when the header is absent.
    """
    raw = x_skene_directory or str(Path.cwd())
    directory = normalize_directory(raw)
    if not Path(directory).is_dir():
        raise HTTPException(status_code=400, detail=f"{DIRECTORY_HEADER}: not a directory: {raw}")
    return directory


def require_auth(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    """Bearer-token check; a no-op when the server was started without a token."""
    token = getattr(request.app.state, "auth_token", None)
    if token is None:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="invalid or missing bearer token")


Services = Annotated[CoreServices, Depends(get_services)]
Directory = Annotated[str, Depends(workspace_directory)]
