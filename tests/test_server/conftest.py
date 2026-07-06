"""Fixtures for HTTP API tests (ASGI in-process, no socket)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from skene.core.services import CoreServices, create_services
from skene.server import create_app


@pytest.fixture
async def services(tmp_path: Path) -> CoreServices:
    def _no_llm():
        raise AssertionError("test did not configure an LLM client")

    built = await create_services(tmp_path / "skene.db", llm_factory=_no_llm)
    yield built
    await built.close()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    directory = tmp_path / "workspace"
    directory.mkdir()
    return directory


@pytest.fixture
def app(services):
    return create_app(services)


@pytest.fixture
async def client(app, workspace):
    transport = httpx.ASGITransport(app=app)
    headers = {"x-skene-directory": str(workspace)}
    async with httpx.AsyncClient(transport=transport, base_url="http://skene.test", headers=headers) as c:
        yield c
